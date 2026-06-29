"""
Volume Surge filter.
Passes when today's volume exceeds N times the average volume over a lookback window.

PineScript equivalent:
    volume > ta.sma(volume, length) * multiplier
"""
import pandas as pd
from src.filters.base import BaseFilter


class VolumeSurgeFilter(BaseFilter):
    name = "volume_surge"
    description = "Today's volume exceeds N× the average volume"
    params = {
        "period": {"type": "int", "default": 20, "label": "Average volume period"},
        "multiplier": {"type": "float", "default": 2.0, "label": "Volume multiplier"},
    }

    def __init__(self, period: int = 20, multiplier: float = 2.0):
        self.period = period
        self.multiplier = multiplier

    def apply(self, df: pd.DataFrame) -> bool:
        if len(df) < self.period + 1:
            return False
        avg_vol = df["volume"].iloc[-(self.period + 1):-1].mean()
        return bool(df["volume"].iloc[-1] > avg_vol * self.multiplier)
