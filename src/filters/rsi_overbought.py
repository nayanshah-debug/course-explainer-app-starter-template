"""
RSI Overbought filter.
Passes when RSI is above the overbought threshold (momentum filter).

PineScript equivalent:
    ta.rsi(close, period) > threshold
"""
import pandas as pd
from src.filters.base import BaseFilter
from src.indicators.rsi import compute_rsi


class RSIOverboughtFilter(BaseFilter):
    name = "rsi_overbought"
    description = "RSI is above overbought threshold (strong momentum)"
    params = {
        "period": {"type": "int", "default": 14, "label": "RSI period"},
        "threshold": {"type": "float", "default": 70.0, "label": "Overbought level"},
    }

    def __init__(self, period: int = 14, threshold: float = 70.0):
        self.period = period
        self.threshold = threshold

    def apply(self, df: pd.DataFrame) -> bool:
        if len(df) < self.period:
            return False
        rsi = compute_rsi(df["close"], self.period)
        return bool(rsi.iloc[-1] > self.threshold)
