"""
Tests for VMC Cipher B filter.
Validates the green-dot (buy) and red-dot (sell) signal logic.
"""
import numpy as np
import pandas as pd
import pytest

from src.filters.pinescript_converted.vmc_cipher_b import VMCCipherBFilter, _compute_wavetrend


def make_ohlcv(close_vals):
    """Build a minimal OHLCV DataFrame from a close price array."""
    close = np.array(close_vals, dtype=float)
    return pd.DataFrame({
        "open":   close * 0.999,
        "high":   close * 1.003,
        "low":    close * 0.997,
        "close":  close,
        "volume": np.ones(len(close)) * 1_000_000,
    })


def downtrend_then_bounce(n=200):
    """
    Sharp downtrend to push WT deep into oversold, then a 1-bar bounce.
    The bounce bar is designed to trigger wt1 crossing above wt2 while wt2 <= -53.
    """
    down = np.linspace(200, 50, n - 1)
    # sharp single-bar spike up — forces wt1 above wt2 on the last bar
    bounce = np.array([down[-1] * 1.08])
    return make_ohlcv(np.concatenate([down, bounce]))


def uptrend_then_rollover(n=200):
    """
    Sharp uptrend to push WT deep into overbought, then a 1-bar drop.
    Designed to trigger wt1 crossing below wt2 while wt2 >= 53.
    """
    up = np.linspace(50, 200, n - 1)
    drop = np.array([up[-1] * 0.92])
    return make_ohlcv(np.concatenate([up, drop]))


# ── Registration ────────────────────────────────────────────────────────────

def test_filter_is_registered():
    from src.filters import FILTER_REGISTRY
    assert "vmc_cipher_b" in FILTER_REGISTRY


def test_name():
    assert VMCCipherBFilter.name == "vmc_cipher_b"


def test_params_schema():
    p = VMCCipherBFilter.params
    assert "buy_signal"  in p
    assert "sell_signal" in p
    assert "ob_level"    in p
    assert "os_level"    in p


# ── Compute WaveTrend ────────────────────────────────────────────────────────

def test_wavetrend_output_shape():
    df = make_ohlcv(np.linspace(100, 200, 150))
    wt1, wt2 = _compute_wavetrend(df, channel_len=9, avg_len=12, ma_len=3)
    assert len(wt1) == len(df)
    assert len(wt2) == len(df)


def test_wavetrend_no_inf():
    df = make_ohlcv(np.linspace(100, 200, 150))
    wt1, wt2 = _compute_wavetrend(df, 9, 12, 3)
    assert not np.isinf(wt1.dropna().values).any()
    assert not np.isinf(wt2.dropna().values).any()


def test_wavetrend_oversold_in_downtrend():
    """Strong downtrend should drive wt2 below -53 at some point."""
    df = downtrend_then_bounce()
    _, wt2 = _compute_wavetrend(df, 9, 12, 3)
    # At least some bars should be oversold
    assert (wt2.dropna() <= -53).any()


def test_wavetrend_overbought_in_uptrend():
    """Strong uptrend should drive wt2 above 53 at some point."""
    df = uptrend_then_rollover()
    _, wt2 = _compute_wavetrend(df, 9, 12, 3)
    assert (wt2.dropna() >= 53).any()


# ── Signal toggles ───────────────────────────────────────────────────────────

def test_both_disabled_always_false():
    df = downtrend_then_bounce()
    f = VMCCipherBFilter(buy_signal=0, sell_signal=0)
    assert f.apply(df) is False


def test_insufficient_data_returns_false():
    df = make_ohlcv(np.linspace(100, 90, 10))
    f = VMCCipherBFilter()
    assert f.apply(df) is False


def test_returns_bool():
    df = downtrend_then_bounce()
    f = VMCCipherBFilter()
    result = f.apply(df)
    assert isinstance(result, bool)


# ── Buy signal (green dot) ───────────────────────────────────────────────────

def test_buy_only_mode_does_not_fire_on_uptrend_rollover():
    """With buy_signal=1, sell_signal=0, a sell setup should NOT pass."""
    df = uptrend_then_rollover()
    f = VMCCipherBFilter(buy_signal=1, sell_signal=0)
    # Even if sell condition is met, it must not fire
    assert f.apply(df) is False


# ── Sell signal (red dot) ────────────────────────────────────────────────────

def test_sell_only_mode_does_not_fire_on_downtrend_bounce():
    """With buy_signal=0, sell_signal=1, a buy setup should NOT pass."""
    df = downtrend_then_bounce()
    f = VMCCipherBFilter(buy_signal=0, sell_signal=1)
    # Even if buy condition is met, it must not fire
    assert f.apply(df) is False


# ── Level configuration ──────────────────────────────────────────────────────

def test_tighter_os_level_harder_to_trigger():
    """Setting os_level to 0 means any wt2 < 0 qualifies as oversold — easier to fire."""
    df = downtrend_then_bounce()
    f_default = VMCCipherBFilter(buy_signal=1, sell_signal=0, os_level=-53)
    f_loose   = VMCCipherBFilter(buy_signal=1, sell_signal=0, os_level=0)
    # The loose version should fire at least as often as the strict version
    # (over same data, loose fires whenever strict does)
    if f_default.apply(df):
        assert f_loose.apply(df)
