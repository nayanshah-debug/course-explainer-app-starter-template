"""
Charles Schwab Market Data provider.
Uses schwab-py (https://schwab-py.readthedocs.io/)

Authentication (one-time setup):
  Run:  python scripts/schwab_auth.py
  This opens a browser for OAuth and saves a token file to env/schwab_token.json.
  Subsequent runs load from the token file automatically.

Required env vars (in env/.env):
  SCHWAB_API_KEY      — App Key from developer.schwab.com
  SCHWAB_API_SECRET   — App Secret from developer.schwab.com
  SCHWAB_CALLBACK_URL — Must match what you set in the Schwab app (e.g. https://127.0.0.1:8182)
  SCHWAB_TOKEN_PATH   — Path to token file (default: env/schwab_token.json)
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from src.data.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Interval string → (FrequencyType string, Frequency int)
_INTERVAL_MAP = {
    "1d":  ("daily",   1),
    "1wk": ("weekly",  1),
    "1mo": ("monthly", 1),
}

# Period string → (PeriodType value, Period value)
_PERIOD_MAP = {
    "1mo":  ("month", 1),
    "3mo":  ("month", 3),
    "6mo":  ("month", 6),
    "1y":   ("year",  1),
    "2y":   ("year",  2),
}


class SchwabProvider(BaseProvider):
    """Market data via Charles Schwab API (requires OAuth token setup)."""

    def __init__(self, api_key: str, api_secret: str, callback_url: str, token_path: str):
        self._api_key      = api_key
        self._api_secret   = api_secret
        self._callback_url = callback_url
        self._token_path   = token_path
        self._client: Optional[object] = None

    def _get_client(self):
        """Load or refresh the Schwab client from the token file."""
        if self._client is not None:
            return self._client

        token_file = Path(self._token_path)
        if not token_file.exists():
            raise FileNotFoundError(
                f"Schwab token file not found at '{token_file}'. "
                "Run:  python scripts/schwab_auth.py  to authenticate."
            )

        import schwab
        self._client = schwab.auth.client_from_token_file(
            token_path=str(token_file),
            api_key=self._api_key,
            app_secret=self._api_secret,
            enforce_enums=False,
        )
        return self._client

    def get_ohlcv(self, ticker: str, interval: str = "1d", period: str = "6mo") -> pd.DataFrame:
        from schwab.client import Client

        PH = Client.PriceHistory

        freq_type_str, freq_val = _INTERVAL_MAP.get(interval, ("daily", 1))
        period_type_str, period_val = _PERIOD_MAP.get(period, ("month", 6))

        # Map string → enum
        period_type_enum = next(e for e in PH.PeriodType   if e.value == period_type_str)
        period_enum      = next(e for e in PH.Period        if e.value == period_val)
        freq_type_enum   = next(e for e in PH.FrequencyType if e.value == freq_type_str)

        try:
            client = self._get_client()
            resp = client.get_price_history(
                ticker,
                period_type=period_type_enum,
                period=period_enum,
                frequency_type=freq_type_enum,
                frequency=freq_val,   # raw int; Frequency enum is minute-only
                need_extended_hours_data=False,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Schwab fetch failed for %s: %s", ticker, exc)
            return pd.DataFrame()

        candles = data.get("candles", [])
        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        # Schwab datetime is milliseconds epoch
        df.index = pd.to_datetime(df["datetime"], unit="ms", utc=True)
        df.index.name = "date"
        df = df.rename(columns={
            "open": "open", "high": "high",
            "low": "low", "close": "close", "volume": "volume",
        })
        return df[["open", "high", "low", "close", "volume"]].astype(float)
