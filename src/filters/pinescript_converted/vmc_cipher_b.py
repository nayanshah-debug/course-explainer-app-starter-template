"""
VMC Cipher B — WaveTrend Signal Filter
Translated from: VuManChu Cipher B Divergences (PineScript v4)

There are TWO types of green/red dots in this indicator:

  1. SMALL CIRCLE  — appears at EVERY WT crossover, plotted at the wt2 level
                     i.e. inside the purple/blue oscillator area
     PineScript:  plot(wtCross ? wt2 : na, color = signalColor)
     Green = wt1 crossed ABOVE wt2 (any level)
     Red   = wt1 crossed BELOW wt2 (any level)
     → use signal_mode = 0

  2. BIG CIRCLE    — appears only when cross happens in extreme OB/OS zone
     PineScript:  plotchar(buySignal ? -107 : na, ...)
     Green = wt1 crossed above wt2 AND wt2 <= osLevel (-53)  ← deep oversold
     Red   = wt1 crossed below wt2 AND wt2 >= obLevel (+53)  ← deep overbought
     → use signal_mode = 1

  3. BOTH          — detect either type
     → use signal_mode = 2

WaveTrend:
  src  = hlc3 = (high + low + close) / 3
  esa  = EMA(src, channel_len)
  de   = EMA(|src - esa|, channel_len)
  ci   = (src - esa) / (0.015 * de)
  wt1  = EMA(ci, avg_len)
  wt2  = SMA(wt1, ma_len)
"""

import pandas as pd
from src.filters.base import BaseFilter
from src.indicators.ema import compute_ema


def _compute_wavetrend(df: pd.DataFrame, channel_len: int, avg_len: int, ma_len: int):
    src = (df["high"] + df["low"] + df["close"]) / 3
    esa = compute_ema(src, channel_len)
    de  = compute_ema((src - esa).abs(), channel_len)
    ci  = (src - esa) / (0.015 * de.replace(0, float("nan")))
    wt1 = compute_ema(ci, avg_len)
    wt2 = wt1.rolling(window=ma_len).mean()
    return wt1, wt2


class VMCCipherBFilter(BaseFilter):
    name        = "vmc_cipher_b"
    description = (
        "VMC Cipher B WaveTrend crossover. "
        "signal_mode: 0=small circle (any cross), 1=big circle (OB/OS zones only), 2=both"
    )
    params = {
        # Which signal type to detect
        "signal_mode":  {"type": "int",   "default": 0,    "label": "Signal mode: 0=small circle, 1=big circle, 2=both"},
        # Direction toggles
        "buy_signal":   {"type": "int",   "default": 1,    "label": "Buy/green dot (1=on, 0=off)"},
        "sell_signal":  {"type": "int",   "default": 0,    "label": "Sell/red dot  (1=on, 0=off)"},
        # How many recent bars to look back
        "lookback":     {"type": "int",   "default": 3,    "label": "Lookback bars (1=last bar only)"},
        # WaveTrend settings
        "channel_len":  {"type": "int",   "default": 9,    "label": "WT Channel Length"},
        "avg_len":      {"type": "int",   "default": 12,   "label": "WT Average Length"},
        "ma_len":       {"type": "int",   "default": 3,    "label": "WT MA Length"},
        # Big circle OB/OS thresholds (only used when signal_mode 1 or 2)
        "ob_level":     {"type": "float", "default": 53.0, "label": "Overbought Level (big circle)"},
        "os_level":     {"type": "float", "default": -53.0,"label": "Oversold Level  (big circle)"},
    }

    def __init__(
        self,
        signal_mode: int   = 0,      # 0=small, 1=big, 2=both
        buy_signal:  int   = 1,
        sell_signal: int   = 0,
        lookback:    int   = 3,
        channel_len: int   = 9,
        avg_len:     int   = 12,
        ma_len:      int   = 3,
        ob_level:    float = 53.0,
        os_level:    float = -53.0,
    ):
        self.signal_mode = signal_mode
        self.buy_signal  = bool(buy_signal)
        self.sell_signal = bool(sell_signal)
        self.lookback    = max(1, lookback)
        self.channel_len = channel_len
        self.avg_len     = avg_len
        self.ma_len      = ma_len
        self.ob_level    = ob_level
        self.os_level    = os_level

    def apply(self, df: pd.DataFrame) -> bool:
        min_bars = self.channel_len + self.avg_len + self.ma_len + 5
        if len(df) < min_bars:
            return False
        if not self.buy_signal and not self.sell_signal:
            return False

        wt1, wt2 = _compute_wavetrend(df, self.channel_len, self.avg_len, self.ma_len)

        valid = wt1.notna() & wt2.notna()
        if valid.sum() < self.lookback + 1:
            return False

        for offset in range(self.lookback):
            i      = -(1 + offset)
            i_prev = -(2 + offset)

            w1_cur  = float(wt1.iloc[i])
            w1_prev = float(wt1.iloc[i_prev])
            w2_cur  = float(wt2.iloc[i])
            w2_prev = float(wt2.iloc[i_prev])

            crossed_up   = w1_cur >= w2_cur and w1_prev < w2_prev
            crossed_down = w1_cur <= w2_cur and w1_prev > w2_prev

            # ── Small circle: any WT crossover (signal_mode 0 or 2) ────────
            if self.signal_mode in (0, 2):
                if self.buy_signal  and crossed_up:
                    self._signal_offset = offset
                    return True
                if self.sell_signal and crossed_down:
                    self._signal_offset = offset
                    return True

            # ── Big circle: crossover in OB/OS zone (signal_mode 1 or 2) ──
            if self.signal_mode in (1, 2):
                if self.buy_signal  and crossed_up   and w2_cur <= self.os_level:
                    self._signal_offset = offset
                    return True
                if self.sell_signal and crossed_down  and w2_cur >= self.ob_level:
                    self._signal_offset = offset
                    return True

        return False
