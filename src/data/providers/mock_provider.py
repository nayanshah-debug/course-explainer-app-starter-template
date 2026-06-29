"""Mock provider for testing — returns deterministic synthetic OHLCV data."""
import numpy as np
import pandas as pd
from src.data.providers.base import BaseProvider


class MockProvider(BaseProvider):
    """Returns synthetic OHLCV data. No network calls. Used in tests."""

    def __init__(self, seed: int = 42):
        self._seed = seed

    def get_ohlcv(self, ticker: str, interval: str = "1d", period: str = "6mo") -> pd.DataFrame:
        rng = np.random.default_rng(hash(ticker + self._seed.__str__()) % (2**32))
        n = 200
        close = 100 + np.cumsum(rng.normal(0, 1, n))
        open_ = close * (1 + rng.normal(0, 0.003, n))
        high = np.maximum(close, open_) * (1 + rng.uniform(0, 0.01, n))
        low = np.minimum(close, open_) * (1 - rng.uniform(0, 0.01, n))
        volume = rng.integers(500_000, 5_000_000, n).astype(float)

        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="B")
        return pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
