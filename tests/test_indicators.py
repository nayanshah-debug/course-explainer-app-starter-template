"""Unit tests for indicator functions."""
import numpy as np
import pandas as pd
import pytest

from src.indicators.ema import compute_ema
from src.indicators.sma import compute_sma
from src.indicators.rsi import compute_rsi
from src.indicators.macd import compute_macd
from src.indicators.bbands import compute_bbands
from src.indicators.atr import compute_atr


def make_close(n=100, seed=0):
    rng = np.random.default_rng(seed)
    return pd.Series(100 + np.cumsum(rng.normal(0, 1, n)))


def make_ohlcv(n=100, seed=0):
    close = make_close(n, seed)
    return pd.DataFrame({
        "open":   close * 0.999,
        "high":   close * 1.005,
        "low":    close * 0.995,
        "close":  close,
        "volume": np.full(n, 1_000_000.0),
    })


class TestEMA:
    def test_length(self):
        close = make_close()
        assert len(compute_ema(close, 9)) == len(close)

    def test_no_nan_after_warmup(self):
        close = make_close(50)
        result = compute_ema(close, 9)
        assert result.iloc[9:].isna().sum() == 0

    def test_converges_faster_than_sma(self):
        # EMA should react more to recent values than SMA
        close = pd.Series([1.0] * 20 + [10.0] * 10)
        ema = compute_ema(close, 10)
        sma = compute_sma(close, 10)
        assert ema.iloc[-1] > sma.iloc[-1]


class TestSMA:
    def test_known_value(self):
        close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        sma = compute_sma(close, 3)
        assert sma.iloc[-1] == pytest.approx(4.0)

    def test_nan_before_warmup(self):
        close = make_close(10)
        sma = compute_sma(close, 5)
        assert sma.iloc[:4].isna().all()
        assert not pd.isna(sma.iloc[4])


class TestRSI:
    def test_length(self):
        close = make_close(100)
        assert len(compute_rsi(close, 14)) == 100

    def test_range(self):
        close = make_close(200)
        rsi = compute_rsi(close, 14).dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_all_up_gives_high_rsi(self):
        close = pd.Series(range(1, 101), dtype=float)
        rsi = compute_rsi(close, 14)
        assert rsi.iloc[-1] > 90

    def test_all_down_gives_low_rsi(self):
        close = pd.Series(range(100, 0, -1), dtype=float)
        rsi = compute_rsi(close, 14)
        assert rsi.iloc[-1] < 10


class TestMACD:
    def test_columns(self):
        close = make_close()
        df = compute_macd(close)
        assert set(df.columns) == {"macd", "signal", "histogram"}

    def test_histogram_identity(self):
        close = make_close()
        df = compute_macd(close)
        diff = (df["macd"] - df["signal"] - df["histogram"]).abs()
        assert diff.max() < 1e-10


class TestBBands:
    def test_columns(self):
        close = make_close()
        bb = compute_bbands(close)
        assert set(bb.columns) == {"upper", "middle", "lower"}

    def test_upper_gt_lower(self):
        close = make_close(100)
        bb = compute_bbands(close, 20).dropna()
        assert (bb["upper"] > bb["lower"]).all()


class TestATR:
    def test_positive(self):
        df = make_ohlcv(100)
        atr = compute_atr(df, 14).dropna()
        assert (atr > 0).all()
