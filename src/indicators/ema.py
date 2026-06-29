"""
Exponential Moving Average.
PineScript equivalent: ta.ema(source, length)
"""
import pandas as pd


def compute_ema(close: pd.Series, period: int) -> pd.Series:
    """Returns EMA series. Uses Wilder's smoothing (adjust=False) to match TradingView."""
    return close.ewm(span=period, adjust=False).mean()
