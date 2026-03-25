# Options Put Scanner — Design Spec
**Date:** 2026-03-25
**Branch:** feature/one

## Overview

Extend TradingScan with a dedicated Options Scanner page that scans all NASDAQ and NYSE stocks for high-probability put-selling opportunities. Results are grouped by expiry date and ranked by a composite profitability score.

---

## Goals

- Scan NASDAQ + NYSE universe for put contracts worth selling
- Filter underlying stocks by price and market cap before fetching options (performance)
- Score each put contract on IV Rank, delta, premium, and liquidity
- Display results on a new dedicated page, grouped by expiry date
- Use the existing Schwab OAuth integration as the options data source

---

## Architecture

### New module: `src/options/`

```
src/options/
  __init__.py
  provider.py      # SchwabOptionsProvider — wraps schwab-py get_option_chain()
  scorer.py        # OptionScorer — computes composite score per put contract
  scanner.py       # OptionsScanner — universe filter + concurrent fetch + score
  result.py        # OptionResult dataclass — one row per qualifying put
  routes.py        # Blueprint: POST /api/options/scan, GET /api/options/scan/<job_id>
```

### Existing files touched (minimally)
- `src/app.py` — register `options` blueprint (1 line)
- `src/views/main.py` — add `/options` page route
- `src/templates/layout.html` — add nav link to Options Scanner
- `src/templates/options.html` — new dedicated page (created)

---

## Data Layer (`options/provider.py`)

`SchwabOptionsProvider` reuses the authenticated client from `SchwabProvider` and calls `get_option_chain()`.

### Underlying stock pre-filter
Before fetching an options chain, call `get_quote()` per ticker to check:
- Stock price ≥ $20
- Market cap ≥ $2B (mid/large cap)

Tickers failing either check are skipped — no options chain fetch needed. This reduces the ~5,000-ticker universe to ~800–1,000 qualifying stocks.

### Option chain fields used per put contract

| Field | Purpose |
|-------|---------|
| `delta` | Strike selection scoring |
| `impliedVolatility` | Per-contract IV, used for IVR calc |
| `bid` / `ask` | Premium received; spread quality guard |
| `openInterest` | Liquidity scoring |
| `totalVolume` | Liquidity scoring |
| `daysToExpiration` | Grouping by expiry |
| `strikePrice` | Display |
| `expirationDate` | Grouping key |
| `historicalVolatility` | 52-week IV range for IVR calculation |

### IV Rank calculation
Schwab does not return IVR directly. It is computed from the option chain response:
```
IVR = (current_IV - 52w_low_IV) / (52w_high_IV - 52w_low_IV) * 100
```
Where `52w_low_IV` and `52w_high_IV` are derived from `historicalVolatility` data in the chain response.

---

## Scoring (`options/scorer.py`)

Each qualifying put contract receives a **composite score from 0–100** based on four equally-weighted components (25 pts each).

| Component | Criteria | Max Pts |
|-----------|----------|---------|
| **IVR Score** | IVR ≥ 50 → 25; IVR 30–50 → linear; IVR < 30 → 0 | 25 |
| **Delta Score** | 0.15–0.20 → 25; 0.10–0.15 or 0.20–0.25 → 15; outside → 0 | 25 |
| **Premium Score** | Bid ≥ $1.00 → 25; $0.50–$1.00 → linear; < $0.50 → 0 | 25 |
| **Liquidity Score** | OI ≥ 500 AND volume ≥ 100 → 25; partial credit below | 25 |

**Minimum threshold:** Contracts scoring below 50/100 are excluded.

**Bid/ask spread guard:** If `(ask - bid) / ask > 10%`, the contract is excluded regardless of score.

---

## Scanner (`options/scanner.py`)

- Accepts `min_price`, `min_market_cap_b`, `min_score` parameters
- Fetches NASDAQ + NYSE universe via existing `src/data/universe.py`
- Pre-filters tickers with `get_quote()` (concurrent, ThreadPoolExecutor)
- Fetches option chains for qualifying tickers (concurrent, ThreadPoolExecutor)
- Scores each put contract via `OptionScorer`
- Returns `List[OptionResult]` sorted by score descending within each expiry group

---

## API (`options/routes.py`)

Follows the same async job pattern as the existing `/api/scan` endpoints.

```
POST /api/options/scan
  Body: {
    "min_price": 20,
    "min_market_cap_b": 2,
    "min_score": 50
  }
  Returns: { "job_id": "<uuid>" }

GET /api/options/scan/<job_id>
  Returns: {
    "status": "running | done | error",
    "completed": 120,
    "total": 950,
    "results": {
      "2026-03-27": [
        {
          "ticker": "AAPL",
          "strike": 210,
          "delta": -0.17,
          "bid": 1.20,
          "ask": 1.30,
          "ivr": 45,
          "oi": 1200,
          "volume": 340,
          "dte": 2,
          "score": 78
        }
      ],
      "2026-04-03": [ ... ]
    }
  }
```

---

## UI (`templates/options.html`)

- **Controls bar:** Min price, min market cap, min score inputs + "Run Scan" button
- **Progress bar:** Live polling via `GET /api/options/scan/<job_id>` (same JS pattern as stock scanner)
- **Results:** Collapsible sections per expiry date, each containing a sortable table
- **Table columns:** Ticker | Strike | Delta | Bid | IVR | OI | Volume | DTE | Score
- **Sortable** by score (default), delta, premium within each expiry group
- Nav link added to existing layout header

---

## Result Dataclass (`options/result.py`)

```python
@dataclass
class OptionResult:
    ticker: str
    strike: float
    expiration: str        # "YYYY-MM-DD"
    dte: int
    delta: float
    bid: float
    ask: float
    iv: float
    ivr: float
    open_interest: int
    volume: int
    score: float

    def to_dict(self) -> dict: ...
```

---

## Testing

- `tests/test_options_scorer.py` — unit tests for each scoring component + edge cases
- `tests/test_options_scanner.py` — integration test with mock Schwab responses
- Mock provider returns synthetic option chains; no live API calls in CI

---

## Out of Scope

- Covered calls, iron condors, or other multi-leg strategies
- Real-time streaming prices (scan is point-in-time)
- Trade execution from the options scanner UI
- Backtesting historical results
