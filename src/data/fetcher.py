"""
Unified data fetcher. Selects the active provider from Config and caches results.
"""
import logging
from typing import List, Optional
import pandas as pd

from src.config import Config
from src.data.cache import get_cache
from src.data.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_provider: Optional[BaseProvider] = None


def get_provider() -> BaseProvider:
    """Returns the configured data provider (singleton)."""
    global _provider
    if _provider is not None:
        return _provider

    name = Config.DATA_PROVIDER
    if name == "yfinance":
        from src.data.providers.yfinance_provider import YFinanceProvider
        _provider = YFinanceProvider()
    elif name == "alphavantage":
        from src.data.providers.alphavantage_provider import AlphaVantageProvider
        _provider = AlphaVantageProvider(Config.ALPHA_VANTAGE_API_KEY)
    elif name == "schwab":
        from src.data.providers.schwab_provider import SchwabProvider
        _provider = SchwabProvider(
            api_key=Config.SCHWAB_API_KEY,
            api_secret=Config.SCHWAB_API_SECRET,
            callback_url=Config.SCHWAB_CALLBACK_URL,
            token_path=Config.SCHWAB_TOKEN_PATH,
        )
    elif name == "polygon":
        from src.data.providers.polygon_provider import PolygonProvider
        _provider = PolygonProvider(Config.POLYGON_API_KEY)
    elif name == "mock":
        from src.data.providers.mock_provider import MockProvider
        _provider = MockProvider()
    else:
        raise ValueError(f"Unknown DATA_PROVIDER: {name}")

    return _provider


def set_provider(provider: BaseProvider) -> None:
    """Override the provider (used in tests)."""
    global _provider
    _provider = provider


def get_ohlcv(ticker: str, interval: str = "1d", period: str = "6mo") -> pd.DataFrame:
    """Fetch OHLCV with caching. Returns empty DataFrame on failure."""
    cache = get_cache(Config.CACHE_TTL_SECONDS)
    key = f"{ticker}:{interval}:{period}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = get_provider().get_ohlcv(ticker, interval, period)
        if not df.empty:
            cache.set(key, df)
        return df
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", ticker, exc)
        return pd.DataFrame()
