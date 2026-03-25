# Options Put Scanner — Design Spec
**Date:** 2026-03-25
**Branch:** feature/one

## Overview

Extend TradingScan with a dedicated Options Scanner page that scans all NASDAQ and NYSE stocks for high-probability put-selling opportunities. Results are grouped by expiry date and ranked by a composite profitability score.

---

## Goals

- Scan NASDAQ + NYSE universe for put contracts worth selling
- Filter underlying stocks by price and market cap before fetching options (performance)
- Score each put contract on IV premium (IV/HV ratio), delta, premium, and liquidity
- Display results on a new dedicated page, grouped by expiry date
- Use the existing Schwab OAuth integration as the options data source

---

## Architecture

### New module: `src/options/`

```
src/options/
  __init__.py
  provider.py      # SchwabOptionsProvider — wraps schwab-py get_option_chain() and get_quotes()
  scorer.py        # OptionScorer — computes composite score per put contract
  scanner.py       # OptionsScanner — universe filter + concurrent fetch + score
  result.py        # OptionResult dataclass — one row per qualifying put
  routes.py        # Blueprint: POST /api/options/scan, GET /api/options/scan/<job_id>
                   # Registered on app with url_prefix="/api/options"
```

### Existing files touched (minimally)
- `src/app.py` — `app.register_blueprint(options_bp, url_prefix="/api/options")` (1 line)
- `src/views/main.py` — add `/options` page route with Schwab token guard
- `src/templates/layout.html` — add nav link to Options Scanner
- `src/templates/options.html` — new dedicated page (created)

---

## Data Layer (`options/provider.py`)

`SchwabOptionsProvider` reuses the authenticated Schwab client. **The client is initialized once** in `__init__` (calling `_get_client()` eagerly before any thread is spawned) to avoid the race condition in the lazy singleton pattern of `SchwabProvider._get_client()`.

```python
class SchwabOptionsProvider:
    def __init__(self, schwab_provider: SchwabProvider):
        self._client = schwab_provider._get_client()  # initialize once, before threads
```

### Underlying stock pre-filter (bulk)

Use Schwab's **bulk `get_quotes()`** endpoint (accepts a list of symbols in one request) rather than individual `get_quote()` calls per ticker. This avoids hitting the 120 req/min rate limit on 5,000 sequential calls.

Batching strategy: split universe into batches of 500 symbols, call `get_quotes()` per batch. This reduces 5,000 individual calls to ~10 batch calls.

Filter criteria per ticker:
- `lastPrice` ≥ `min_price` (default $20)
- `marketCap` ≥ `min_market_cap_b * 1e9` (default $2B)
- **If `marketCap` is `null` or missing** (ETFs, ADRs, some small caps): **skip the ticker** — treat as failing the market cap filter

**ETF handling:** `get_all_us_tickers()` includes ETFs alongside stocks. ETFs commonly return null `marketCap` from `get_quotes()` and are therefore skipped by the null check above. ETFs that do return a valid `marketCap` (some large equity ETFs) will pass the pre-filter and may be included in the scan — this is acceptable since they have liquid options chains. The null-marketCap skip is the sole gating mechanism for ETFs; no additional ETF exclusion logic is needed.

This reduces the ~5,000-ticker universe to ~800–1,000 qualifying stocks.

### Option chain fetch

After pre-filtering, fetch option chains concurrently via `ThreadPoolExecutor`. The already-initialized client is shared safely because `schwab-py` client calls are individually thread-safe (each call is an independent HTTP request).

### IV calculation note

Schwab `get_option_chain()` does **not** return a 52-week IV high/low range, so true IV Rank (IVR) cannot be computed from a single API call. Instead, use an **IV/HV ratio** as a proxy for "elevated implied volatility":

```
iv_premium = option.impliedVolatility / chain.volatility
```

Where:
- `option.impliedVolatility` — the put contract's current IV (from options chain)
- `chain.volatility` — the underlying stock's 30-day historical volatility (top-level field in chain response)

An `iv_premium > 1.2` means the market is pricing in more volatility than recent history — equivalent to a moderately elevated IVR. This is used in the scoring component described below.

### Option chain fields used per put contract

| Field | Purpose |
|-------|---------|
| `delta` | Strike selection scoring |
| `impliedVolatility` | Per-contract IV (for IV/HV ratio) |
| `bid` / `ask` | Premium received; spread quality guard |
| `openInterest` | Liquidity scoring (serialized as `oi`) |
| `totalVolume` | Liquidity scoring |
| `daysToExpiration` | Grouping by expiry; DTE filter |
| `strikePrice` | Display |
| `expirationDate` | Grouping key |
| chain-level `volatility` | 30-day HV of underlying (denominator for IV/HV ratio) |

---

## Scoring (`options/scorer.py`)

Each qualifying put contract receives a **composite score from 0–100** based on four equally-weighted components (25 pts each).

| Component | Criteria | Max Pts |
|-----------|----------|---------|
| **IV Premium Score** | iv_premium ≥ 1.5 → 25; 1.2–1.5 → linear; < 1.2 → 0 | 25 |
| **Delta Score** | abs(delta) 0.15–0.20 → 25; 0.10–0.15 or 0.20–0.25 → 15; outside → 0 | 25 |
| **Premium Score** | bid ≥ $1.00 → 25; $0.50–$1.00 → linear (bid - 0.50) / 0.50 * 25; < $0.50 → 0 | 25 |
| **Liquidity Score** | `min(OI/500, 1) * 12.5 + min(volume/100, 1) * 12.5` | 25 |

**Minimum threshold:** Contracts scoring below 50/100 are excluded.

**Bid/ask spread guard:** If `(ask - bid) / ask > 10%`, the contract is excluded regardless of score.

**DTE filter:** Contracts with `daysToExpiration < 1` (same-day expiry) or `daysToExpiration > 45` are excluded. This targets the 7–45 DTE sweet spot for weekly/monthly put selling.

---

## Scanner (`options/scanner.py`)

Parameters:
- `min_price: float = 20.0`
- `min_market_cap_b: float = 2.0`
- `min_score: float = 50.0`

Steps:
1. Fetch universe via `get_all_us_tickers(min_price=4.0)` — always use the default `4.0` argument to avoid evicting the existing `@lru_cache(maxsize=1)` entry used by the stock scanner (which also calls this function with `min_price=4.0`). The `min_price` parameter of the options scanner is enforced in step 2 via `get_quotes()`, not at the universe level.
2. Pre-filter by price ≥ `min_price` AND market cap ≥ threshold using bulk `get_quotes()` batches of 500 — skip tickers with null `marketCap` or below threshold
3. Fetch option chains for qualifying tickers concurrently (ThreadPoolExecutor, same `SCAN_CONCURRENCY` config)
4. For each put contract: apply DTE filter, spread guard, score via `OptionScorer`
5. Exclude contracts below `min_score`
6. Return `List[OptionResult]` sorted by score descending within each expiry group

---

## API (`options/routes.py`)

Registered with `url_prefix="/api/options"` in `src/app.py`.

Follows the same async job pattern as the existing `/api/scan` endpoints, with a modified internal job dict to accommodate grouped results.

### Internal job dict structure
```python
def _make_job():
    return {
        "status":    "running",      # running | done | error
        "completed": 0,
        "total":     0,
        "matched":   0,
        "results":   {},             # dict[expiry_date_str, list[dict]] — NOT a flat list
        "error":     None,
    }
```

### Endpoints

```
POST /api/options/scan
  Body: {
    "min_price": 20,
    "min_market_cap_b": 2,
    "min_score": 50
  }
  Returns: { "job_id": "<uuid>" }

GET /api/options/scan/<job_id>
  Returns (success): {
    "status": "running | done",
    "completed": 120,
    "total": 950,
    "matched": 34,
    "results": {
      "2026-03-27": [
        {
          "ticker": "AAPL",
          "strike": 210.0,
          "delta": -0.17,
          "bid": 1.20,
          "ask": 1.30,
          "iv": 0.28,
          "iv_premium": 1.4,
          "oi": 1200,
          "volume": 340,
          "dte": 2,
          "score": 78.0
        }
      ],
      "2026-04-03": [ ... ]
    },
    "error": null
  }

  Returns (error): {
    "status": "error",
    "error": "<message>",
    "completed": 0, "total": 0, "matched": 0, "results": {}
  }
```

---

## Result Dataclass (`options/result.py`)

```python
@dataclass
class OptionResult:
    ticker: str
    strike: float
    expiration: str        # "YYYY-MM-DD" — used as grouping key
    dte: int
    delta: float           # negative for puts (e.g. -0.17)
    bid: float
    ask: float
    iv: float              # implied volatility as decimal (e.g. 0.28 = 28%)
    iv_premium: float      # iv / historical_volatility ratio
    oi: int                # open interest (field name matches JSON key "oi")
    volume: int
    score: float

    def to_dict(self) -> dict:
        return {
            "ticker":     self.ticker,
            "expiration": self.expiration,  # included so routes.py can group by this key
            "strike":     self.strike,
            "delta":      self.delta,
            "bid":        self.bid,
            "ask":        self.ask,
            "iv":         self.iv,
            "iv_premium": self.iv_premium,
            "oi":         self.oi,
            "volume":     self.volume,
            "dte":        self.dte,
            "score":      round(self.score, 1),
        }
```

**Grouping in `routes.py`:** The progress callback calls `result.to_dict()` and groups the resulting dict by its `"expiration"` key into `job["results"]`:

```python
def on_progress(completed, total, result):
    with _jobs_lock:
        job = _jobs[job_id]
        job["completed"] = completed
        job["total"] = total
        if result is not None:
            d = result.to_dict()
            job["results"].setdefault(d["expiration"], []).append(d)
            job["matched"] += 1
```

---

## UI (`templates/options.html`)

- **Auth guard:** If Schwab token is missing or expired, show inline error with link to `/auth/schwab/start` — do not redirect automatically
- **Controls bar:** Min price, min market cap, min score inputs + "Run Scan" button
- **Progress bar:** Live polling via `GET /api/options/scan/<job_id>` (same JS pattern as stock scanner)
- **Results:** Collapsible sections per expiry date (sorted ascending), each containing a sortable table
- **Table columns:** Ticker | Strike | Delta | Bid | IV | IV Premium | OI | Volume | DTE | Score
- **Default sort:** Score descending within each expiry group
- Nav link added to existing layout header

---

## Testing

- `tests/test_options_scorer.py` — unit tests for each scoring component + edge cases (null delta, zero OI, wide spread)
- `tests/test_options_scanner.py` — integration test with mock Schwab responses (no live API calls in CI)
- Mock provider returns synthetic option chains with known fields to validate end-to-end scoring and grouping

---

## Out of Scope

- True IV Rank (IVR) from 52-week IV history — IV/HV ratio used as proxy instead
- Covered calls, iron condors, or other multi-leg strategies
- Real-time streaming prices (scan is point-in-time)
- Trade execution from the options scanner UI
- Backtesting historical results
