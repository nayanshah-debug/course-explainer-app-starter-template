"""
RSI Oversold filter.
Passes when RSI crosses above the oversold threshold (recovery signal).

PineScript equivalent:
    ta.crossover(ta.rsi(close, period), threshold)
"""
import pandas as pd
from src.filters.base import BaseFilter
from src.indicators.rsi import compute_rsi


class RSIOversoldFilter(BaseFilter):
    name = "rsi_oversold"
    description = "RSI crosses above oversold threshold (recovery from oversold)"
    params = {
        "period": {"type": "int", "default": 14, "label": "RSI period"},
        "threshold": {"type": "float", "default": 30.0, "label": "Oversold level"},
    }

    def __init__(self, period: int = 14, threshold: float = 30.0):
        self.period = period
        self.threshold = threshold

    def apply(self, df: pd.DataFrame) -> bool:
        if len(df) < self.period + 1:
            return False
        rsi = compute_rsi(df["close"], self.period)
        return bool(rsi.iloc[-1] > self.threshold and rsi.iloc[-2] <= self.threshold)
