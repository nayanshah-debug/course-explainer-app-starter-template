"""
Simple Moving Average.
PineScript equivalent: ta.sma(source, length)
"""
import pandas as pd


def compute_sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=period).mean()
