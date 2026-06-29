"""
Bollinger Bands.
PineScript equivalent: ta.bb(source, length, mult)
"""
import pandas as pd
from src.indicators.sma import compute_sma


def compute_bbands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    """
    Returns DataFrame with columns:
        upper  — upper band
        middle — middle band (SMA)
        lower  — lower band
    """
    middle = compute_sma(close, period)
    std = close.rolling(window=period).std()
    return pd.DataFrame(
        {"upper": middle + std_dev * std, "middle": middle, "lower": middle - std_dev * std}
    )
