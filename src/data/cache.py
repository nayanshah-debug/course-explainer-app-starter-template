"""Simple in-memory TTL cache for OHLCV DataFrames."""
import time
from typing import Optional
import pandas as pd


class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._store: dict = {}

    def get(self, key: str) -> Optional[pd.DataFrame]:
        entry = self._store.get(key)
        if entry is None:
            return None
        df, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return df

    def set(self, key: str, df: pd.DataFrame) -> None:
        self._store[key] = (df, time.monotonic() + self._ttl)

    def clear(self) -> None:
        self._store.clear()


# Module-level singleton; replaced with a fresh instance in tests
_cache: Optional[TTLCache] = None


def get_cache(ttl_seconds: int = 300) -> TTLCache:
    global _cache
    if _cache is None:
        _cache = TTLCache(ttl_seconds)
    return _cache
