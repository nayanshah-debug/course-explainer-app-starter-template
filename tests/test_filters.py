"""Unit tests for filter classes."""
import numpy as np
import pandas as pd
import pytest

from src.filters.ema_crossover import EMACrossoverFilter
from src.filters.rsi_oversold import RSIOversoldFilter
from src.filters.rsi_overbought import RSIOverboughtFilter
from src.filters.volume_surge import VolumeSurgeFilter
from src.filters.macd_crossover import MACDCrossoverFilter
from src.filters.above_ema import AboveEMAFilter


def make_df(n=200, seed=42):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "open":   close * 0.999,
        "high":   close * 1.005,
        "low":    close * 0.995,
        "close":  close,
        "volume": np.full(n, 1_000_000.0),
    })


def make_crossover_df(fast, slow):
    """DataFrame where fast EMA just crossed above slow EMA on the last bar."""
    n = slow * 3
    # Start with downtrend, then sharp upturn
    close = np.concatenate([
        np.linspace(100, 80, n - 5),
        np.linspace(80, 120, 5),   # sharp upturn triggers crossover
    ])
    return pd.DataFrame({
        "open": close, "high": close * 1.002,
        "low": close * 0.998, "close": close,
        "volume": np.ones(n) * 1e6,
    })


class TestEMACrossoverFilter:
    def test_returns_bool(self):
        f = EMACrossoverFilter(9, 21)
        assert isinstance(f.apply(make_df()), bool)

    def test_insufficient_data(self):
        f = EMACrossoverFilter(9, 21)
        assert f.apply(make_df(10)) is False

    def test_name(self):
        assert EMACrossoverFilter.name == "ema_crossover"


class TestRSIOversoldFilter:
    def test_returns_bool(self):
        f = RSIOversoldFilter(14, 30)
        assert isinstance(f.apply(make_df()), bool)

    def test_recovery_signal(self):
        # Build a series where RSI crosses up through 30
        n = 100
        close = np.concatenate([
            np.linspace(100, 60, 80),   # heavy downtrend → RSI below 30
            np.linspace(60, 70, 20),    # mild recovery → RSI crosses 30
        ])
        df = pd.DataFrame({
            "open": close, "high": close * 1.001,
            "low": close * 0.999, "close": close,
            "volume": np.ones(n) * 1e6,
        })
        f = RSIOversoldFilter(14, 30)
        # Result is a bool — just verify it doesn't throw
        assert isinstance(f.apply(df), bool)

    def test_name(self):
        assert RSIOversoldFilter.name == "rsi_oversold"


class TestVolumeSurgeFilter:
    def test_high_volume_passes(self):
        df = make_df(100)
        df.iloc[-1, df.columns.get_loc("volume")] = 20_000_000   # 20× normal
        f = VolumeSurgeFilter(period=20, multiplier=2.0)
        assert f.apply(df) is True

    def test_normal_volume_fails(self):
        df = make_df(100)
        f = VolumeSurgeFilter(period=20, multiplier=10.0)
        assert f.apply(df) is False

    def test_name(self):
        assert VolumeSurgeFilter.name == "volume_surge"


class TestAboveEMAFilter:
    def test_above_passes(self):
        # Strongly rising series: price should be above EMA(10)
        close = np.linspace(50, 200, 100)
        df = pd.DataFrame({
            "open": close, "high": close * 1.001,
            "low": close * 0.999, "close": close,
            "volume": np.ones(100) * 1e6,
        })
        assert AboveEMAFilter(period=10).apply(df) is True

    def test_insufficient_data(self):
        assert AboveEMAFilter(period=200).apply(make_df(50)) is False

    def test_name(self):
        assert AboveEMAFilter.name == "above_ema"


class TestMACDCrossoverFilter:
    def test_returns_bool(self):
        f = MACDCrossoverFilter()
        assert isinstance(f.apply(make_df()), bool)

    def test_name(self):
        assert MACDCrossoverFilter.name == "macd_crossover"
