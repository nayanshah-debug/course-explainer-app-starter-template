import pandas as pd
import yfinance as yf
from src.data.providers.base import BaseProvider


class YFinanceProvider(BaseProvider):
    """Free data provider using Yahoo Finance (no API key required)."""

    def get_ohlcv(self, ticker: str, interval: str = "1d", period: str = "6mo") -> pd.DataFrame:
        data = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            multi_level_index=False,  # newer yfinance returns MultiIndex; flatten it
        )
        if data.empty:
            return pd.DataFrame()

        # Flatten MultiIndex columns if present (e.g. ('Close', 'AAPL') → 'close')
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0].lower() for col in data.columns]
        else:
            data.columns = [c.lower() for c in data.columns]

        data.index.name = "date"
        return data[["open", "high", "low", "close", "volume"]]
