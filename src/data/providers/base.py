from abc import ABC, abstractmethod
import pandas as pd


class BaseProvider(ABC):
    """All data providers must implement this interface."""

    @abstractmethod
    def get_ohlcv(self, ticker: str, interval: str = "1d", period: str = "6mo") -> pd.DataFrame:
        """
        Fetch OHLCV data for a ticker.

        Args:
            ticker: Stock symbol e.g. "AAPL"
            interval: Bar interval e.g. "1d", "1h", "5m"
            period: Lookback period e.g. "6mo", "1y", "60d"

        Returns:
            DataFrame with lowercase columns: open, high, low, close, volume
            Index: DatetimeIndex (UTC)
        """
        ...
