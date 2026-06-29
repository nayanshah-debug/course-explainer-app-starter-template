# PineScript Converted Filters

Drop converted PineScript filters here. Each file is auto-discovered on startup.

## Template

```python
# filters/pinescript_converted/my_strategy.py
import pandas as pd
from src.filters.base import BaseFilter
from src.indicators.ema import compute_ema
from src.indicators.rsi import compute_rsi


class MyStrategyFilter(BaseFilter):
    name = "my_strategy"           # unique snake_case ID used in API
    description = "Short description shown in the UI"
    params = {
        "ema_period": {"type": "int",   "default": 21,   "label": "EMA Period"},
        "rsi_level":  {"type": "float", "default": 50.0, "label": "RSI Level"},
    }

    def __init__(self, ema_period: int = 21, rsi_level: float = 50.0):
        self.ema_period = ema_period
        self.rsi_level  = rsi_level

    def apply(self, df: pd.DataFrame) -> bool:
        close = df["close"]
        ema   = compute_ema(close, self.ema_period)
        rsi   = compute_rsi(close, 14)
        # PineScript: close > ta.ema(close, ema_period) and ta.rsi(close,14) > rsi_level
        return bool(close.iloc[-1] > ema.iloc[-1] and rsi.iloc[-1] > self.rsi_level)
```

## PineScript → Python cheat sheet

| PineScript | Python |
|---|---|
| `ta.ema(close, n)` | `compute_ema(df["close"], n)` |
| `ta.sma(close, n)` | `compute_sma(df["close"], n)` |
| `ta.rsi(close, n)` | `compute_rsi(df["close"], n)` |
| `ta.macd(close, f, s, sig)` | `compute_macd(df["close"], f, s, sig)` — returns df with `macd`, `signal`, `histogram` |
| `ta.atr(n)` | `compute_atr(df, n)` |
| `ta.bb(close, n, mult)` | `compute_bbands(df["close"], n, mult)` — returns df with `upper`, `middle`, `lower` |
| `ta.crossover(a, b)` | `self.crossover(a_series, b_series)` |
| `ta.crossunder(a, b)` | `self.crossunder(a_series, b_series)` |
| `close[1]` (previous bar) | `df["close"].iloc[-2]` |
| `barstate.islast` | always true — filters evaluate on the last bar |

## VMC Cipher B — `signal_mode` parameter

The VMC Cipher B filter (`vmc_cipher_b`) supports two distinct signal types from the original PineScript.
Use the `signal_mode` param to control which one is required for a match:

| `signal_mode` | Signal type | PineScript equivalent | Condition |
|---|---|---|---|
| `0` *(default)* | **Small circle** — any WT crossover | `plotchar(wtCross, ...)` | `wt1` crosses `wt2` at any level |
| `1` | **Big circle** — oversold/overbought WT cross | `plot(wtVwap, ...)` | `wt1` crosses `wt2` **and** `wt2 ≤ -53` (buy) or `wt2 ≥ +53` (sell) |
| `2` | **Either** — small or big circle | both conditions | matches if either type fires |

**Why this matters**: The green dot visible on a TradingView chart for a stock like HOOD is typically the *small circle* (`signal_mode=0`) — a WaveTrend crossover at any level. The *big circle* (`signal_mode=1`) only triggers deep in oversold/overbought territory (WT2 ≤ −53 / ≥ +53) and is rarer.

Use `lookback` (default `3`) to check the last N bars. A value of `1` checks only the most recent bar; increase it to catch signals from the last few candles.
