"""
Relative Volume (RVOL) filter.
Passes when today's volume is >= N times the average volume over a lookback period.

RVOL = current_volume / avg_volume(period)

PineScript equivalent:
    volume / ta.sma(volume, period) >= min_rvol
"""
import pandas as pd
from src.filters.base import BaseFilter


class RelativeVolumeFilter(BaseFilter):
    name = "relative_volume"
    description = "Current volume ≥ N× the average volume (RVOL filter)"
    params = {
        "period":   {"type": "int",   "default": 20,  "label": "Avg volume period (bars)"},
        "min_rvol": {"type": "float", "default": 1.5, "label": "Min relative volume (e.g. 1.5 = 150%)"},
    }

    def __init__(self, period: int = 20, min_rvol: float = 1.5):
        self.period   = period
        self.min_rvol = min_rvol

    def apply(self, df: pd.DataFrame) -> bool:
        if len(df) < self.period + 1:
            return False
        # Average volume over the N bars before today
        avg_vol = df["volume"].iloc[-(self.period + 1):-1].mean()
        if avg_vol == 0:
            return False
        rvol = df["volume"].iloc[-1] / avg_vol
        return bool(rvol >= self.min_rvol)
