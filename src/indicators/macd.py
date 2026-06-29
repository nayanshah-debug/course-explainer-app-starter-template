"""
MACD — Moving Average Convergence Divergence.
PineScript equivalent: ta.macd(source, fast, slow, signal)
"""
import pandas as pd
from src.indicators.ema import compute_ema


def compute_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """
    Returns DataFrame with columns:
        macd     — MACD line (fast EMA - slow EMA)
        signal   — Signal line (EMA of MACD)
        histogram — MACD - signal
    """
    macd_line = compute_ema(close, fast) - compute_ema(close, slow)
    signal_line = compute_ema(macd_line, signal)
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "histogram": macd_line - signal_line}
    )
