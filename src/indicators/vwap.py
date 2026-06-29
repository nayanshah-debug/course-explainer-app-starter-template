"""
Volume Weighted Average Price.
PineScript equivalent: ta.vwap(source)
"""
import pandas as pd


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Expects df with columns: high, low, close, volume. Resets daily."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum()
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    return cum_tp_vol / cum_vol
