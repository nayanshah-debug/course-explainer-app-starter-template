"""
EMA Crossover filter.
Passes when the fast EMA crosses above the slow EMA on the most recent bar.

PineScript equivalent:
    ta.crossover(ta.ema(close, fast), ta.ema(close, slow))
"""
import pandas as pd
from src.filters.base import BaseFilter
from src.indicators.ema import compute_ema


class EMACrossoverFilter(BaseFilter):
    name = "ema_crossover"
    description = "Fast EMA crosses above Slow EMA (bullish crossover)"
    params = {
        "fast": {"type": "int", "default": 9, "label": "Fast EMA period"},
        "slow": {"type": "int", "default": 21, "label": "Slow EMA period"},
    }

    def __init__(self, fast: int = 9, slow: int = 21):
        self.fast = fast
        self.slow = slow

    def apply(self, df: pd.DataFrame) -> bool:
        if len(df) < self.slow + 1:
            return False
        close = df["close"]
        ema_fast = compute_ema(close, self.fast)
        ema_slow = compute_ema(close, self.slow)
        return self.crossover(ema_fast, ema_slow)
