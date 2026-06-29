"""
Schwab OAuth web flow.

Routes (all under /auth):
  GET  /auth/schwab/status      — token state: connected | expired | no_token
  GET  /auth/schwab/start       — generate auth URL, store state in session
  POST /auth/schwab/complete    — exchange redirect URL for token, save to disk
  POST /auth/schwab/disconnect  — delete token, reset provider singleton
"""
import json
import time
from pathlib import Path

from flask import Blueprint, jsonify, request, session

from src.config import Config
from src.data import fetcher

bp = Blueprint("auth", __name__)

# Schwab refresh tokens last 7 days
_REFRESH_TTL_DAYS = 7


def _token_write_func(token_path: str):
    """Returns a write function compatible with schwab-py's token format."""
    def write(token, *args, **kwargs):
        with open(token_path, "w") as f:
            json.dump(token, f)
    return write


def _token_status():
    """
    Returns (connected: bool, reason: str, age_days: float|None)
    Reasons: ok | no_token | expired | invalid
    """
    path = Path(Config.SCHWAB_TOKEN_PATH)
    if not path.exists():
        return False, "no_token", None
    try:
        data = json.loads(path.read_text())
        ts = data.get("creation_timestamp")
        if ts is None:
            return False, "invalid", None
        age_days = (time.time() - ts) / 86400
        if age_days > _REFRESH_TTL_DAYS:
            return False, "expired", round(age_days, 1)
        return True, "ok", round(age_days, 1)
    except Exception:
        return False, "invalid", None


@bp.get("/schwab/status")
def schwab_status():
    provider = Config.DATA_PROVIDER
    if provider != "schwab":
        return jsonify({
            "provider": provider,
            "schwab_active": False,
            "connected": None,
        })
    connected, reason, age_days = _token_status()
    return jsonify({
        "provider": "schwab",
        "schwab_active": True,
        "connected": connected,
        "reason": reason,
        "token_age_days": age_days,
    })


@bp.get("/schwab/start")
def schwab_start():
    """Generate Schwab authorization URL and store OAuth state in session."""
    if Config.DATA_PROVIDER != "schwab":
        return jsonify({"error": "DATA_PROVIDER is not schwab"}), 400
    if not Config.SCHWAB_API_KEY:
        return jsonify({"error": "SCHWAB_API_KEY not configured in env/.env"}), 400

    try:
        import schwab.auth
        auth_context = schwab.auth.get_auth_context(
            Config.SCHWAB_API_KEY,
            Config.SCHWAB_CALLBACK_URL,
        )
        session["schwab_state"]        = auth_context.state
        session["schwab_callback_url"] = auth_context.callback_url
        return jsonify({"auth_url": auth_context.authorization_url})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.post("/schwab/complete")
def schwab_complete():
    """
    Exchange the pasted post-login redirect URL for an access token.
    Saves the token to disk and resets the provider singleton.
    """
    body = request.get_json(force=True) or {}
    redirect_url = (body.get("redirect_url") or "").strip()
    if not redirect_url:
        return jsonify({"error": "redirect_url is required"}), 400

    state        = session.get("schwab_state")
    callback_url = session.get("schwab_callback_url")
    if not state or not callback_url:
        return jsonify({"error": "Session expired — please restart the login flow."}), 400

    try:
        import schwab.auth

        # Reconstruct AuthContext from session — authorization_url is not
        # needed for the token-exchange step, only callback_url and state are.
        auth_context = schwab.auth.AuthContext(
            callback_url=callback_url,
            authorization_url="",
            state=state,
        )

        token_path = Path(Config.SCHWAB_TOKEN_PATH)
        token_path.parent.mkdir(parents=True, exist_ok=True)

        schwab.auth.client_from_received_url(
            api_key=Config.SCHWAB_API_KEY,
            app_secret=Config.SCHWAB_API_SECRET,
            auth_context=auth_context,
            received_url=redirect_url,
            token_write_func=_token_write_func(str(token_path)),
        )

        # Reset provider singleton so next request loads the new token
        fetcher._provider = None

        session.pop("schwab_state", None)
        session.pop("schwab_callback_url", None)

        return jsonify({"success": True})

    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/schwab/disconnect")
def schwab_disconnect():
    """Delete the token file and reset the data provider."""
    try:
        path = Path(Config.SCHWAB_TOKEN_PATH)
        if path.exists():
            path.unlink()
        fetcher._provider = None
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
