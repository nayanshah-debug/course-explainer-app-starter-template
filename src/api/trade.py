"""
Robinhood trading endpoints.

Required env vars (in env/.env):
  ROBINHOOD_USERNAME  — your Robinhood email
  ROBINHOOD_PASSWORD  — your Robinhood password

First-time login: POST /trade/rh/login with {"mfa_code": "123456"}
Subsequent logins use the stored session pickle automatically.
"""
import logging

from flask import Blueprint, jsonify, request

from src.config import Config

logger = logging.getLogger(__name__)

bp = Blueprint("trade", __name__)


def _rh():
    """Import robin_stocks lazily so the app still starts if not installed."""
    try:
        import robin_stocks.robinhood as r
        return r
    except ImportError:
        raise RuntimeError(
            "robin_stocks is not installed. Run: pip install robin_stocks"
        )


def _login(r):
    """Login using stored session."""
    r.login(
        username=Config.RH_USERNAME,
        password=Config.RH_PASSWORD,
        store_session=True,
        mfa_code=None,
    )


@bp.get("/rh/status")
def rh_status():
    """Return whether a valid Robinhood session exists."""
    if not Config.RH_USERNAME or not Config.RH_PASSWORD:
        return jsonify({"connected": False, "reason": "no_credentials"})
    try:
        r = _rh()
        _login(r)
        profile = r.profiles.load_account_profile()
        connected = bool(profile and profile.get("account_number"))
        return jsonify({"connected": connected, "reason": "ok" if connected else "login_failed"})
    except Exception as exc:
        return jsonify({"connected": False, "reason": str(exc)})


@bp.post("/rh/login")
def rh_login():
    """
    Login with optional MFA code (required on first login or after session expires).
    Body: {"mfa_code": "123456"}  — omit if reusing stored session.
    """
    if not Config.RH_USERNAME or not Config.RH_PASSWORD:
        return jsonify({"error": "ROBINHOOD_USERNAME / ROBINHOOD_PASSWORD not set in env/.env"}), 400

    data = request.get_json(silent=True) or {}
    mfa_code = data.get("mfa_code") or None

    try:
        r = _rh()
        r.login(
            username=Config.RH_USERNAME,
            password=Config.RH_PASSWORD,
            store_session=True,
            mfa_code=mfa_code,
        )
        profile = r.profiles.load_account_profile()
        if not profile or not profile.get("account_number"):
            return jsonify({"error": "Login succeeded but could not load account. Check credentials."}), 401
        return jsonify({"status": "ok"})
    except Exception as exc:
        logger.warning("Robinhood login failed: %s", exc)
        return jsonify({"error": str(exc)}), 401


@bp.post("/rh/logout")
def rh_logout():
    try:
        r = _rh()
        r.logout()
    except Exception:
        pass
    return jsonify({"status": "ok"})


@bp.get("/rh/quote/<ticker>")
def rh_quote(ticker: str):
    """
    Return bid, ask, and midpoint for a ticker.
    Used to pre-fill the limit price in the buy modal.
    """
    ticker = ticker.upper().strip()
    try:
        r = _rh()
        _login(r)
        quotes = r.stocks.get_quotes(ticker)
        if not quotes or not quotes[0]:
            return jsonify({"error": f"No quote data for {ticker}"}), 404

        q = quotes[0]
        bid = float(q.get("bid_price") or 0)
        ask = float(q.get("ask_price") or 0)

        # Fall back to last trade price if bid/ask are zero (after-hours)
        last = float(q.get("last_trade_price") or q.get("last_extended_hours_trade_price") or 0)
        if bid <= 0 or ask <= 0:
            mid = last
        else:
            mid = (bid + ask) / 2

        return jsonify({
            "ticker": ticker,
            "bid":    round(bid, 4),
            "ask":    round(ask, 4),
            "mid":    round(mid, 4),
            "last":   round(last, 4),
        })
    except Exception as exc:
        logger.warning("Quote failed for %s: %s", ticker, exc)
        return jsonify({"error": str(exc)}), 500


@bp.post("/rh/buy")
def rh_buy():
    """
    Place a limit buy order at a specified limit price.
    Body: {"ticker": "AAPL", "quantity": 5, "limit_price": 213.45}
    """
    data = request.get_json(silent=True) or {}
    ticker      = (data.get("ticker") or "").upper().strip()
    quantity    = data.get("quantity")
    limit_price = data.get("limit_price")

    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid quantity: {exc}"}), 400
    try:
        limit_price = round(float(limit_price), 2)
        if limit_price <= 0:
            raise ValueError("limit_price must be > 0")
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid limit_price: {exc}"}), 400

    try:
        r = _rh()
        _login(r)
        order = r.orders.order_buy_limit(ticker, quantity, limit_price)
        if not order:
            return jsonify({"error": "No response from Robinhood"}), 500
        order_id = order.get("id") or order.get("client_id") or "unknown"
        return jsonify({
            "status":      "ok",
            "order_id":    order_id,
            "ticker":      ticker,
            "quantity":    quantity,
            "limit_price": limit_price,
        })
    except Exception as exc:
        logger.warning("Robinhood buy failed for %s qty %s @ %s: %s", ticker, quantity, limit_price, exc)
        return jsonify({"error": str(exc)}), 500
