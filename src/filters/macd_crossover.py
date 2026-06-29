"""
MACD Crossover filter.
Passes when the MACD line crosses above the signal line (bullish signal).

PineScript equivalent:
    ta.crossover(macdLine, signalLine)
    where [macdLine, signalLine, _] = ta.macd(close, fast, slow, signal)
"""
import pandas as pd
from src.filters.base import BaseFilter
from src.indicators.macd import compute_macd


class MACDCrossoverFilter(BaseFilter):
    name = "macd_crossover"
    description = "MACD line crosses above signal line (bullish)"
    params = {
        "fast": {"type": "int", "default": 12, "label": "Fast EMA period"},
        "slow": {"type": "int", "default": 26, "label": "Slow EMA period"},
        "signal": {"type": "int", "default": 9, "label": "Signal period"},
    }

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def apply(self, df: pd.DataFrame) -> bool:
        if len(df) < self.slow + self.signal:
            return False
        macd_df = compute_macd(df["close"], self.fast, self.slow, self.signal)
        return self.crossover(macd_df["macd"], macd_df["signal"])
