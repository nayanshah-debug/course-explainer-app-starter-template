"""
Price Above EMA filter.
Passes when the closing price is above EMA(period).

PineScript equivalent:
    close > ta.ema(close, period)
"""
import pandas as pd
from src.filters.base import BaseFilter
from src.indicators.ema import compute_ema


class AboveEMAFilter(BaseFilter):
    name = "above_ema"
    description = "Closing price is above EMA"
    params = {
        "period": {"type": "int", "default": 200, "label": "EMA period"},
    }

    def __init__(self, period: int = 200):
        self.period = period

    def apply(self, df: pd.DataFrame) -> bool:
        if len(df) < 2:
            return False
        ema = compute_ema(df["close"], self.period)
        last_ema = ema.iloc[-1]
        if pd.isna(last_ema):
            return False
        return bool(df["close"].iloc[-1] > last_ema)
