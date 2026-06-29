# Options Put Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated Options Scanner page to TradingScan that scans NASDAQ + NYSE stocks via Schwab API, scores put contracts by IV premium, delta, bid, and liquidity, and displays results grouped by expiry date.

**Architecture:** New `src/options/` module (result → scorer → provider → scanner → routes) wired into the existing Flask app with a new `/options` page. Reuses the existing Schwab OAuth client, universe fetcher, and async job/polling pattern from the stock scanner.

**Tech Stack:** Python 3, Flask, schwab-py, ThreadPoolExecutor, Jinja2, vanilla JS

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/options/__init__.py` | Create | Empty package marker |
| `src/options/result.py` | Create | `OptionResult` dataclass + `to_dict()` |
| `src/options/scorer.py` | Create | `OptionScorer` — 4-component 0–100 score |
| `src/options/provider.py` | Create | `SchwabOptionsProvider` — bulk quotes pre-filter + option chain fetch |
| `src/options/scanner.py` | Create | `OptionsScanner` — orchestrates universe → pre-filter → chain fetch → score |
| `src/options/routes.py` | Create | Flask blueprint: async scan job pattern, `/api/options/scan` endpoints |
| `src/templates/options.html` | Create | Options Scanner page (extends layout.html) |
| `src/app.py` | Modify | Register options blueprint |
| `src/views/main.py` | Modify | Add `/options` page route with auth guard |
| `src/templates/layout.html` | Modify | Add Options nav link |
| `tests/test_options_scorer.py` | Create | Unit tests for scoring logic |
| `tests/test_options_scanner.py` | Create | Integration tests with mock Schwab client |
| `tests/test_options_api.py` | Create | Flask test client tests for API endpoints |

---

## Task 1: `OptionResult` dataclass

**Files:**
- Create: `src/options/__init__.py`
- Create: `src/options/result.py`
- Create: `tests/test_options_scorer.py` (start file, add first test)

- [ ] **Step 1: Create the package marker**

```python
# src/options/__init__.py
# (empty)
```

- [ ] **Step 2: Write a failing test for `OptionResult.to_dict()`**

```python
# tests/test_options_scorer.py
from src.options.result import OptionResult


def make_result(**overrides):
    defaults = dict(
        ticker="AAPL", strike=210.0, expiration="2026-03-28",
        dte=3, delta=-0.17, bid=1.20, ask=1.30,
        iv=0.28, iv_premium=1.4, oi=1200, volume=340, score=78.0,
    )
    defaults.update(overrides)
    return OptionResult(**defaults)


def test_to_dict_keys():
    d = make_result().to_dict()
    expected_keys = {
        "ticker", "expiration", "strike", "delta", "bid", "ask",
        "iv", "iv_premium", "oi", "volume", "dte", "score",
    }
    assert set(d.keys()) == expected_keys


def test_to_dict_score_rounded():
    d = make_result(score=78.456).to_dict()
    assert d["score"] == 78.5


def test_to_dict_expiration_present():
    d = make_result(expiration="2026-04-03").to_dict()
    assert d["expiration"] == "2026-04-03"
```

- [ ] **Step 3: Run test to verify it fails**

```
pytest tests/test_options_scorer.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.options.result'`

- [ ] **Step 4: Implement `OptionResult`**

```python
# src/options/result.py
from dataclasses import dataclass


@dataclass
class OptionResult:
    ticker: str
    strike: float
    expiration: str       # "YYYY-MM-DD" — used as grouping key in routes
    dte: int
    delta: float          # negative for puts (e.g. -0.17)
    bid: float
    ask: float
    iv: float             # implied volatility as decimal (e.g. 0.28 = 28%)
    iv_premium: float     # iv / underlying_historical_volatility
    oi: int               # open interest
    volume: int
    score: float

    def to_dict(self) -> dict:
        return {
            "ticker":     self.ticker,
            "expiration": self.expiration,
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

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_options_scorer.py -v
```
Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/options/__init__.py src/options/result.py tests/test_options_scorer.py
git commit -m "feat(options): add OptionResult dataclass"
```

---

## Task 2: `OptionScorer`

**Files:**
- Create: `src/options/scorer.py`
- Modify: `tests/test_options_scorer.py` (add scorer tests)

- [ ] **Step 1: Write failing tests for each scoring component**

Append to `tests/test_options_scorer.py`:

```python
from src.options.scorer import OptionScorer


class TestIVPremiumScore:
    def test_above_1_5_max(self):
        assert OptionScorer.iv_premium_score(1.5) == 25.0
    def test_above_1_5_still_max(self):
        assert OptionScorer.iv_premium_score(2.0) == 25.0
    def test_at_1_2_zero(self):
        assert OptionScorer.iv_premium_score(1.2) == 0.0
    def test_below_1_2_zero(self):
        assert OptionScorer.iv_premium_score(1.0) == 0.0
    def test_midpoint_linear(self):
        # 1.35 is halfway between 1.2 and 1.5 → 12.5
        score = OptionScorer.iv_premium_score(1.35)
        assert abs(score - 12.5) < 0.01


class TestDeltaScore:
    def test_sweet_spot(self):
        assert OptionScorer.delta_score(-0.17) == 25.0
    def test_outer_band(self):
        assert OptionScorer.delta_score(-0.12) == 15.0
    def test_too_far_otm(self):
        assert OptionScorer.delta_score(-0.05) == 0.0
    def test_too_close_atm(self):
        assert OptionScorer.delta_score(-0.30) == 0.0
    def test_positive_delta_uses_abs(self):
        # Schwab sometimes returns positive deltas for puts
        assert OptionScorer.delta_score(0.17) == 25.0


class TestPremiumScore:
    def test_above_1_max(self):
        assert OptionScorer.premium_score(1.00) == 25.0
    def test_above_1_still_max(self):
        assert OptionScorer.premium_score(2.50) == 25.0
    def test_below_0_5_zero(self):
        assert OptionScorer.premium_score(0.40) == 0.0
    def test_midpoint_linear(self):
        # 0.75 is halfway between 0.50 and 1.00 → 12.5
        score = OptionScorer.premium_score(0.75)
        assert abs(score - 12.5) < 0.01


class TestLiquidityScore:
    def test_full_score(self):
        assert OptionScorer.liquidity_score(500, 100) == 25.0
    def test_zero_oi(self):
        assert OptionScorer.liquidity_score(0, 100) == 12.5
    def test_zero_volume(self):
        assert OptionScorer.liquidity_score(500, 0) == 12.5
    def test_both_zero(self):
        assert OptionScorer.liquidity_score(0, 0) == 0.0
    def test_above_max_capped(self):
        assert OptionScorer.liquidity_score(10000, 10000) == 25.0


class TestCompositeScore:
    def test_sum_of_components(self):
        result = make_result(iv_premium=1.5, delta=-0.17, bid=1.00, oi=500, volume=100)
        score = OptionScorer.score(result)
        assert score == 100.0

    def test_spread_guard_excludes(self):
        # bid=0.80, ask=2.00 → spread = 60% > 10% → score = 0
        result = make_result(bid=0.80, ask=2.00, iv_premium=2.0, delta=-0.17, oi=500, volume=100)
        assert OptionScorer.score(result) == 0.0

    def test_dte_below_1_excluded(self):
        result = make_result(dte=0, iv_premium=2.0, delta=-0.17, bid=1.00, oi=500, volume=100)
        assert OptionScorer.score(result) == 0.0

    def test_dte_above_45_excluded(self):
        result = make_result(dte=46, iv_premium=2.0, delta=-0.17, bid=1.00, oi=500, volume=100)
        assert OptionScorer.score(result) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_options_scorer.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.options.scorer'`

- [ ] **Step 3: Implement `OptionScorer`**

```python
# src/options/scorer.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.options.result import OptionResult


class OptionScorer:
    @staticmethod
    def iv_premium_score(iv_premium: float) -> float:
        """IV/HV ratio component. Max 25 pts."""
        if iv_premium < 1.2:
            return 0.0
        if iv_premium >= 1.5:
            return 25.0
        return (iv_premium - 1.2) / (1.5 - 1.2) * 25.0

    @staticmethod
    def delta_score(delta: float) -> float:
        """Delta component (uses abs value). Max 25 pts."""
        d = abs(delta)
        if 0.15 <= d <= 0.20:
            return 25.0
        if (0.10 <= d < 0.15) or (0.20 < d <= 0.25):
            return 15.0
        return 0.0

    @staticmethod
    def premium_score(bid: float) -> float:
        """Bid premium component. Max 25 pts."""
        if bid >= 1.00:
            return 25.0
        if bid < 0.50:
            return 0.0
        return (bid - 0.50) / 0.50 * 25.0

    @staticmethod
    def liquidity_score(oi: int, volume: int) -> float:
        """Open interest + volume component. Max 25 pts."""
        return min(oi / 500, 1.0) * 12.5 + min(volume / 100, 1.0) * 12.5

    @staticmethod
    def score(result: "OptionResult") -> float:
        """
        Composite 0–100 score.
        Returns 0 if DTE out of range [1, 45] or bid/ask spread > 10%.
        """
        if result.dte < 1 or result.dte > 45:
            return 0.0
        if result.ask > 0 and (result.ask - result.bid) / result.ask > 0.10:
            return 0.0

        return (
            OptionScorer.iv_premium_score(result.iv_premium)
            + OptionScorer.delta_score(result.delta)
            + OptionScorer.premium_score(result.bid)
            + OptionScorer.liquidity_score(result.oi, result.volume)
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_options_scorer.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/options/scorer.py tests/test_options_scorer.py
git commit -m "feat(options): add OptionScorer with 4-component scoring"
```

---

## Task 3: `SchwabOptionsProvider`

**Files:**
- Create: `src/options/provider.py`
- Create: `tests/test_options_scanner.py` (start file, add provider tests)

**Key Schwab API shapes:**

`get_quotes(['AAPL', ...]).json()` returns:
```json
{
  "AAPL": {
    "quote": { "lastPrice": 215.0 },
    "fundamental": { "marketCap": 3200000000000.0 }
  }
}
```

`get_option_chain('AAPL', contractType='PUT').json()` returns:
```json
{
  "volatility": 0.22,
  "putExpDateMap": {
    "2026-03-28:3": {
      "210.0": [{
        "delta": -0.17, "impliedVolatility": 0.28,
        "bid": 1.20, "ask": 1.30,
        "openInterest": 1200, "totalVolume": 340,
        "daysToExpiration": 3, "strikePrice": 210.0,
        "expirationDate": "2026-03-28"
      }]
    }
  }
}
```

- [ ] **Step 1: Write failing tests for pre-filter and chain parsing**

```python
# tests/test_options_scanner.py
from unittest.mock import MagicMock, patch
from src.options.provider import SchwabOptionsProvider


def _make_quotes_response(data: dict):
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def _make_chain_response(volatility: float, puts: dict):
    resp = MagicMock()
    resp.json.return_value = {
        "volatility": volatility,
        "putExpDateMap": puts,
    }
    resp.raise_for_status.return_value = None
    return resp


def _make_provider():
    mock_schwab = MagicMock()
    mock_schwab._get_client.return_value = MagicMock()
    return SchwabOptionsProvider(mock_schwab)


class TestPreFilter:
    def test_passes_qualifying_ticker(self):
        provider = _make_provider()
        provider._client.get_quotes.return_value = _make_quotes_response({
            "AAPL": {"quote": {"lastPrice": 215.0}, "fundamental": {"marketCap": 3.2e12}}
        })
        result = provider.pre_filter(["AAPL"], min_price=20.0, min_market_cap_b=2.0)
        assert "AAPL" in result

    def test_excludes_low_price(self):
        provider = _make_provider()
        provider._client.get_quotes.return_value = _make_quotes_response({
            "CHEAP": {"quote": {"lastPrice": 5.0}, "fundamental": {"marketCap": 3e9}}
        })
        result = provider.pre_filter(["CHEAP"], min_price=20.0, min_market_cap_b=2.0)
        assert "CHEAP" not in result

    def test_excludes_low_market_cap(self):
        provider = _make_provider()
        provider._client.get_quotes.return_value = _make_quotes_response({
            "SMALL": {"quote": {"lastPrice": 50.0}, "fundamental": {"marketCap": 5e8}}
        })
        result = provider.pre_filter(["SMALL"], min_price=20.0, min_market_cap_b=2.0)
        assert "SMALL" not in result

    def test_excludes_null_market_cap(self):
        provider = _make_provider()
        provider._client.get_quotes.return_value = _make_quotes_response({
            "ETF": {"quote": {"lastPrice": 50.0}, "fundamental": {"marketCap": None}}
        })
        result = provider.pre_filter(["ETF"], min_price=20.0, min_market_cap_b=2.0)
        assert "ETF" not in result

    def test_batches_500_at_a_time(self):
        provider = _make_provider()
        provider._client.get_quotes.return_value = _make_quotes_response({})
        tickers = [f"T{i}" for i in range(1200)]
        provider.pre_filter(tickers, min_price=20.0, min_market_cap_b=2.0)
        # 1200 tickers → 3 batches of 500/500/200
        assert provider._client.get_quotes.call_count == 3


class TestGetPuts:
    def test_parses_put_contracts(self):
        provider = _make_provider()
        provider._client.get_option_chain.return_value = _make_chain_response(
            volatility=0.22,
            puts={
                "2026-03-28:3": {
                    "210.0": [{
                        "delta": -0.17, "impliedVolatility": 0.28,
                        "bid": 1.20, "ask": 1.30,
                        "openInterest": 1200, "totalVolume": 340,
                        "daysToExpiration": 3, "strikePrice": 210.0,
                        "expirationDate": "2026-03-28",
                    }]
                }
            }
        )
        results = provider.get_puts("AAPL")
        assert len(results) == 1
        r = results[0]
        assert r.ticker == "AAPL"
        assert r.strike == 210.0
        assert r.delta == -0.17
        # Use tolerance for float division (round() results can differ by tiny amounts)
        assert abs(r.iv_premium - round(0.28 / 0.22, 4)) < 0.0001
        assert r.oi == 1200

    def test_returns_empty_on_missing_put_map(self):
        provider = _make_provider()
        provider._client.get_option_chain.return_value = _make_chain_response(
            volatility=0.22, puts={}
        )
        assert provider.get_puts("AAPL") == []

    def test_skips_on_api_error(self):
        provider = _make_provider()
        provider._client.get_option_chain.side_effect = Exception("API error")
        assert provider.get_puts("AAPL") == []

    def test_zero_volatility_skips_contract(self):
        """Avoid division by zero when chain.volatility == 0."""
        provider = _make_provider()
        provider._client.get_option_chain.return_value = _make_chain_response(
            volatility=0.0,
            puts={"2026-03-28:3": {"210.0": [{"delta": -0.17, "impliedVolatility": 0.28,
                "bid": 1.20, "ask": 1.30, "openInterest": 100, "totalVolume": 50,
                "daysToExpiration": 3, "strikePrice": 210.0, "expirationDate": "2026-03-28"}]}}
        )
        assert provider.get_puts("AAPL") == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_options_scanner.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.options.provider'`

- [ ] **Step 3: Implement `SchwabOptionsProvider`**

```python
# src/options/provider.py
import logging
from typing import List

from src.data.providers.schwab_provider import SchwabProvider
from src.options.result import OptionResult

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


class SchwabOptionsProvider:
    def __init__(self, schwab_provider: SchwabProvider):
        # Initialize client eagerly before threads are spawned to avoid
        # the race condition in SchwabProvider._get_client()'s lazy singleton.
        self._client = schwab_provider._get_client()

    def pre_filter(
        self,
        tickers: List[str],
        min_price: float,
        min_market_cap_b: float,
    ) -> List[str]:
        """
        Return tickers where lastPrice >= min_price AND marketCap >= threshold.
        Uses bulk get_quotes() in batches of 500 to avoid rate limits.
        Tickers with null/missing marketCap are excluded.
        """
        qualifying = []
        min_cap = min_market_cap_b * 1e9

        for i in range(0, len(tickers), _BATCH_SIZE):
            batch = tickers[i : i + _BATCH_SIZE]
            try:
                resp = self._client.get_quotes(batch)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("get_quotes batch failed: %s", exc)
                continue

            for ticker in batch:
                quote_data = data.get(ticker)
                if not quote_data:
                    continue
                last_price = (quote_data.get("quote") or {}).get("lastPrice") or 0.0
                market_cap = (quote_data.get("fundamental") or {}).get("marketCap")
                if market_cap is None:
                    continue
                if last_price >= min_price and market_cap >= min_cap:
                    qualifying.append(ticker)

        return qualifying

    def get_puts(self, ticker: str) -> List[OptionResult]:
        """
        Fetch and parse all put contracts for a single ticker.
        Returns empty list on any error.
        """
        try:
            resp = self._client.get_option_chain(
                ticker,
                contractType="PUT",
                includeUnderlyingQuote=False,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("get_option_chain failed for %s: %s", ticker, exc)
            return []

        hv = data.get("volatility") or 0.0
        if hv == 0.0:
            return []  # cannot compute iv_premium without HV

        results = []
        put_map = data.get("putExpDateMap") or {}

        for _exp_key, strikes in put_map.items():
            for _strike_key, contracts in strikes.items():
                for contract in contracts:
                    iv = contract.get("impliedVolatility") or 0.0
                    bid = contract.get("bid") or 0.0
                    ask = contract.get("ask") or 0.0
                    oi = int(contract.get("openInterest") or 0)
                    volume = int(contract.get("totalVolume") or 0)
                    dte = int(contract.get("daysToExpiration") or 0)
                    strike = float(contract.get("strikePrice") or 0.0)
                    expiration = contract.get("expirationDate") or ""
                    delta = float(contract.get("delta") or 0.0)

                    results.append(OptionResult(
                        ticker=ticker,
                        strike=strike,
                        expiration=expiration,
                        dte=dte,
                        delta=delta,
                        bid=bid,
                        ask=ask,
                        iv=round(iv, 4),
                        iv_premium=round(iv / hv, 4),
                        oi=oi,
                        volume=volume,
                        score=0.0,  # scored separately
                    ))

        return results
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_options_scanner.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/options/provider.py tests/test_options_scanner.py
git commit -m "feat(options): add SchwabOptionsProvider with pre-filter and chain parsing"
```

---

## Task 4: `OptionsScanner`

**Files:**
- Create: `src/options/scanner.py`
- Modify: `tests/test_options_scanner.py` (add scanner tests)

- [ ] **Step 1: Write failing tests for the scanner**

Append to `tests/test_options_scanner.py`:

```python
from src.options.scanner import OptionsScanner


def _make_scanner_with_mock_provider(put_results):
    """Return a scanner whose provider returns fixed put results."""
    mock_provider = MagicMock()
    mock_provider.pre_filter.return_value = ["AAPL"]
    mock_provider.get_puts.return_value = put_results

    scanner = OptionsScanner.__new__(OptionsScanner)
    scanner._provider = mock_provider
    return scanner


class TestOptionsScanner:
    def _high_score_result(self):
        from src.options.result import OptionResult
        return OptionResult(
            ticker="AAPL", strike=210.0, expiration="2026-03-28",
            dte=7, delta=-0.17, bid=1.20, ask=1.30,
            iv=0.33, iv_premium=1.5, oi=500, volume=100, score=0.0,
        )

    def test_score_is_computed_and_set(self):
        scanner = _make_scanner_with_mock_provider([self._high_score_result()])
        results = scanner.run(["AAPL"], min_price=20.0, min_market_cap_b=2.0, min_score=0.0)
        assert all(r.score > 0 for r in results)

    def test_below_min_score_excluded(self):
        from src.options.result import OptionResult
        low_score = OptionResult(
            ticker="AAPL", strike=300.0, expiration="2026-03-28",
            dte=7, delta=-0.03, bid=0.10, ask=0.20,
            iv=0.20, iv_premium=0.9, oi=5, volume=1, score=0.0,
        )
        scanner = _make_scanner_with_mock_provider([low_score])
        results = scanner.run(["AAPL"], min_price=20.0, min_market_cap_b=2.0, min_score=50.0)
        assert results == []

    def test_results_sorted_by_score_desc(self):
        from src.options.result import OptionResult
        high = OptionResult("AAPL", 210.0, "2026-03-28", 7, -0.17, 1.20, 1.30,
                            0.33, 1.5, 500, 100, 0.0)
        low  = OptionResult("AAPL", 220.0, "2026-03-28", 7, -0.12, 0.60, 0.70,
                            0.25, 1.3, 200, 50, 0.0)
        scanner = _make_scanner_with_mock_provider([low, high])
        results = scanner.run(["AAPL"], min_price=20.0, min_market_cap_b=2.0, min_score=0.0)
        assert results[0].score >= results[1].score
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_options_scanner.py::TestOptionsScanner -v
```
Expected: `ModuleNotFoundError: No module named 'src.options.scanner'`

- [ ] **Step 3: Implement `OptionsScanner`**

```python
# src/options/scanner.py
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

from src.config import Config
from src.data.universe import get_all_us_tickers
from src.data.providers.schwab_provider import SchwabProvider
from src.data import fetcher
from src.options.provider import SchwabOptionsProvider
from src.options.result import OptionResult
from src.options.scorer import OptionScorer

logger = logging.getLogger(__name__)


class OptionsScanner:
    def __init__(self):
        schwab = fetcher.get_provider()
        if not isinstance(schwab, SchwabProvider):
            raise RuntimeError(
                "Options scanner requires DATA_PROVIDER=schwab. "
                f"Current provider: {type(schwab).__name__}"
            )
        self._provider = SchwabOptionsProvider(schwab)

    def run(
        self,
        universe: List[str],
        min_price: float = 20.0,
        min_market_cap_b: float = 2.0,
        min_score: float = 50.0,
        progress_callback: Optional[Callable[[int, int, Optional[OptionResult]], None]] = None,
    ) -> List[OptionResult]:
        """
        Scan universe: pre-filter by price+market-cap, fetch option chains,
        score each put, return qualifying results sorted by score descending.
        """
        qualifying = self._provider.pre_filter(universe, min_price, min_market_cap_b)
        total = len(qualifying)
        completed = 0
        all_results: List[OptionResult] = []

        with ThreadPoolExecutor(max_workers=Config.SCAN_CONCURRENCY) as pool:
            futures = {
                pool.submit(self._scan_ticker, ticker): ticker
                for ticker in qualifying
            }
            for future in as_completed(futures):
                ticker = futures[future]
                new_results = []
                try:
                    new_results = future.result()
                except Exception as exc:
                    logger.warning("Error scanning options for %s: %s", ticker, exc)

                all_results.extend(new_results)
                completed += 1

                if progress_callback:
                    best = max(new_results, key=lambda r: r.score, default=None)
                    qualified_best = best if (best and best.score >= min_score) else None
                    progress_callback(completed, total, qualified_best)

        qualified = [r for r in all_results if r.score >= min_score]
        return sorted(qualified, key=lambda r: r.score, reverse=True)

    def _scan_ticker(self, ticker: str) -> List[OptionResult]:
        puts = self._provider.get_puts(ticker)
        for put in puts:
            put.score = OptionScorer.score(put)
        return puts
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_options_scanner.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/options/scanner.py tests/test_options_scanner.py
git commit -m "feat(options): add OptionsScanner with concurrent chain fetching and scoring"
```

---

## Task 5: API routes

**Files:**
- Create: `src/options/routes.py`
- Create: `tests/test_options_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_options_api.py
import json
import time
from unittest.mock import patch, MagicMock
import pytest
from src.app import create_app
from src.data import fetcher
from src.data.providers.mock_provider import MockProvider


# Use a distinct fixture name to avoid collision with conftest.py's `client` fixture.
@pytest.fixture
def options_client():
    app = create_app({"TESTING": True, "DATA_PROVIDER": "mock"})
    fetcher.set_provider(MockProvider())   # prevent live network calls in background thread
    return app.test_client()


def test_scan_returns_job_id(options_client):
    # Patch at the module level where OptionsScanner is imported (routes.py top-level import)
    with patch("src.options.routes.OptionsScanner") as MockScanner:
        MockScanner.return_value.run.return_value = []
        resp = options_client.post("/api/options/scan",
            data=json.dumps({"min_price": 20, "min_market_cap_b": 2, "min_score": 50}),
            content_type="application/json")
    assert resp.status_code == 200
    assert "job_id" in resp.get_json()


def test_scan_status_not_found(options_client):
    resp = options_client.get("/api/options/scan/nonexistent-job-id")
    assert resp.status_code == 404


def test_scan_status_shape(options_client):
    with patch("src.options.routes.OptionsScanner") as MockScanner:
        MockScanner.return_value.run.return_value = []
        resp = options_client.post("/api/options/scan",
            data=json.dumps({}), content_type="application/json")
        job_id = resp.get_json()["job_id"]

    # Poll until done (max 3 seconds) to avoid flaky sleep-based synchronization
    for _ in range(30):
        status = options_client.get(f"/api/options/scan/{job_id}").get_json()
        if status.get("status") in ("done", "error"):
            break
        time.sleep(0.1)

    assert "status" in status
    assert "results" in status
    assert isinstance(status["results"], dict)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_options_api.py -v
```
Expected: failures (blueprint not registered yet)

- [ ] **Step 3: Implement `options/routes.py`**

```python
# src/options/routes.py
import threading
import uuid
import logging

from flask import Blueprint, jsonify, request

from src.data.universe import get_all_us_tickers
# Import at module level so patch("src.options.routes.OptionsScanner") resolves correctly in tests
from src.options.scanner import OptionsScanner

logger = logging.getLogger(__name__)
bp = Blueprint("options", __name__)

_jobs: dict = {}
_jobs_lock = threading.Lock()


def _make_job():
    return {
        "status":    "running",
        "completed": 0,
        "total":     0,
        "matched":   0,
        "results":   {},    # dict[expiry_str, list[dict]] — NOT a flat list
        "error":     None,
    }


def _run_job(job_id: str, min_price: float, min_market_cap_b: float, min_score: float):
    def on_progress(completed, total, result):
        with _jobs_lock:
            job = _jobs[job_id]
            job["completed"] = completed
            job["total"] = total
            if result is not None:
                d = result.to_dict()
                job["results"].setdefault(d["expiration"], []).append(d)
                job["matched"] += 1

    try:
        universe = get_all_us_tickers(min_price=4.0)
        scanner = OptionsScanner()
        scanner.run(
            universe,
            min_price=min_price,
            min_market_cap_b=min_market_cap_b,
            min_score=min_score,
            progress_callback=on_progress,
        )
        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
    except Exception as exc:
        logger.error("Options scan job %s failed: %s", job_id, exc)
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(exc)


@bp.post("/scan")
def scan():
    body = request.get_json(force=True) or {}
    min_price        = float(body.get("min_price", 20.0))
    min_market_cap_b = float(body.get("min_market_cap_b", 2.0))
    min_score        = float(body.get("min_score", 50.0))

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = _make_job()

    t = threading.Thread(
        target=_run_job,
        args=(job_id, min_price, min_market_cap_b, min_score),
        daemon=True,
    )
    t.start()
    return jsonify({"job_id": job_id})


@bp.get("/scan/<job_id>")
def scan_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)
```

- [ ] **Step 4: Register blueprint in `src/app.py`**

Add after the existing blueprint imports and registrations:

```python
from src.options.routes import bp as options_bp
app.register_blueprint(options_bp, url_prefix="/api/options")
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_options_api.py -v
```
Expected: all PASSED

- [ ] **Step 6: Run full test suite to ensure no regressions**

```
pytest tests/ --ignore=tests/e2e -v
```
Expected: all PASSED

- [ ] **Step 7: Commit**

```bash
git add src/options/routes.py src/app.py tests/test_options_api.py
git commit -m "feat(options): add async scan API blueprint at /api/options"
```

---

## Task 6: Page route and nav link

**Files:**
- Modify: `src/views/main.py`
- Modify: `src/templates/layout.html`

- [ ] **Step 1: Replace the contents of `src/views/main.py` with the following**

(The existing file has only the `index` route. We are replacing the whole file to add the `options` route — do not append, as this would create a duplicate `bp = Blueprint(...)` definition.)

```python
# src/views/main.py
from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/options")
def options():
    from src.api.auth import _token_status
    connected, reason, _ = _token_status()
    return render_template("options.html", schwab_connected=connected, schwab_reason=reason)
```

- [ ] **Step 2: Add nav link in `src/templates/layout.html`**

In the `<nav class="navbar">` section, after the logo div, add a nav links bar. Find this block:

```html
      <div class="nav-logo">
```

And add nav links after the logo's closing `</div>`, before `<div class="nav-right">`:

```html
      <div class="nav-links">
        <a class="nav-link {% if request.path == '/' %}nav-link-active{% endif %}" href="/">STOCK SCANNER</a>
        <a class="nav-link {% if request.path == '/options' %}nav-link-active{% endif %}" href="/options">OPTIONS SCANNER</a>
      </div>
```

- [ ] **Step 3: Manually test that `/options` route renders without error**

Start the app:
```
flask --app src/app.py run
```
Visit `http://localhost:5000/options` — should render (even if Schwab not connected).

- [ ] **Step 4: Commit**

```bash
git add src/views/main.py src/templates/layout.html
git commit -m "feat(options): add /options page route and nav link"
```

---

## Task 7: Options Scanner UI page

**Files:**
- Create: `src/templates/options.html`

The page extends `layout.html`. Follow the same cyberpunk/terminal aesthetic as `index.html` (same CSS classes: `scanner-layout`, `control-panel`, `panel-header`, `param-group`, `run-btn`, `results-panel`, `progress-bar-wrap`, `results-table`, `result-row`, etc.).

- [ ] **Step 1: Create `src/templates/options.html`**

```html
{% extends "layout.html" %}

{% block title %}TradingScan — Options Scanner{% endblock %}

{% block content %}
<div class="scanner-layout">

  <!-- CONTROL PANEL -->
  <aside class="control-panel">
    <div class="panel-header">
      <span class="panel-label">// OPTIONS SCAN PARAMETERS</span>
    </div>

    {% if not schwab_connected %}
    <div class="schwab-warn">
      <span class="warn-icon">⚠</span>
      Schwab not connected.
      <a href="#" onclick="document.getElementById('schwab-action-btn').click(); return false;">Connect Schwab</a>
      to use the options scanner.
    </div>
    {% endif %}

    <div class="param-group">
      <label class="param-title">MIN STOCK PRICE ($)</label>
      <input class="param-number-input" id="min-price" type="number" value="20" min="1" step="1" />
    </div>

    <div class="param-group">
      <label class="param-title">MIN MARKET CAP ($ Billions)</label>
      <input class="param-number-input" id="min-mktcap" type="number" value="2" min="0.1" step="0.5" />
    </div>

    <div class="param-group">
      <label class="param-title">MIN SCORE (0–100)</label>
      <input class="param-number-input" id="min-score" type="number" value="50" min="0" max="100" step="5" />
    </div>

    <button class="run-btn" id="run-btn" {% if not schwab_connected %}disabled{% endif %}>
      <span class="run-btn-text">&#9654; RUN OPTIONS SCAN</span>
    </button>
  </aside>

  <!-- RESULTS PANEL -->
  <section class="results-panel">
    <div class="panel-header results-header">
      <span class="panel-label">// OPTIONS SCAN RESULTS</span>
      <div class="stats-bar" id="stats-bar" style="display:none">
        <span id="stat-progress"></span>
        <span id="stat-matched" class="accent-green">—</span> contracts &nbsp;|&nbsp;
        <span id="stat-time">—</span>ms
      </div>
    </div>

    <!-- Idle -->
    <div class="results-idle" id="results-idle">
      <div class="idle-grid"></div>
      <div class="idle-text">
        <span class="idle-icon">◈</span>
        <p>Set parameters and run an options scan.</p>
        <p class="idle-sub">Scans NASDAQ + NYSE for high-probability put-selling opportunities.</p>
      </div>
    </div>

    <!-- Progress -->
    <div class="results-loading" id="results-loading" style="display:none">
      <div class="spinner-ring"></div>
      <div class="loading-text">SCANNING OPTIONS<span class="dot-anim">...</span></div>
      <div class="progress-bar-wrap">
        <div class="progress-bar-track">
          <div class="progress-bar-fill" id="progress-bar-fill"></div>
        </div>
        <div class="progress-label" id="progress-label">0 / 0</div>
      </div>
    </div>

    <!-- Results grouped by expiry -->
    <div id="results-groups" style="display:none"></div>

    <!-- No results -->
    <div id="results-empty" style="display:none" class="results-empty">
      <span class="empty-icon">◌</span>
      <p>No qualifying put contracts found.</p>
    </div>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
(function () {
  'use strict';

  let _pollTimer = null;

  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function showState(state) {
    document.getElementById('results-idle').style.display     = state === 'idle'    ? '' : 'none';
    document.getElementById('results-loading').style.display  = state === 'loading' ? '' : 'none';
    document.getElementById('results-groups').style.display   = state === 'table'   ? '' : 'none';
    document.getElementById('results-empty').style.display    = state === 'empty'   ? '' : 'none';
  }

  document.getElementById('run-btn').addEventListener('click', function () {
    const btn = this;
    btn.disabled = true;
    btn.querySelector('.run-btn-text').textContent = '⏳ SCANNING...';

    if (_pollTimer) { clearTimeout(_pollTimer); _pollTimer = null; }
    showState('loading');

    document.getElementById('progress-bar-fill').style.width = '0%';
    document.getElementById('progress-label').textContent = '0 / 0';
    document.getElementById('stats-bar').style.display = '';
    document.getElementById('stat-progress').textContent = '0 / 0 scanned  ';
    document.getElementById('stat-matched').textContent = '0';
    document.getElementById('stat-time').textContent = '—';
    document.getElementById('results-groups').innerHTML = '';

    const payload = {
      min_price:        parseFloat(document.getElementById('min-price').value) || 20,
      min_market_cap_b: parseFloat(document.getElementById('min-mktcap').value) || 2,
      min_score:        parseFloat(document.getElementById('min-score').value) || 50,
    };

    const t0 = performance.now();

    fetch('/api/options/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        pollJob(data.job_id, t0, btn);
      })
      .catch(err => {
        showState('idle');
        alert('Scan failed: ' + err.message);
        btn.disabled = false;
        btn.querySelector('.run-btn-text').textContent = '▶ RUN OPTIONS SCAN';
      });
  });

  function pollJob(jobId, t0, btn) {
    function tick() {
      fetch('/api/options/scan/' + jobId)
        .then(r => r.json())
        .then(job => {
          const completed = job.completed || 0;
          const total     = job.total     || 0;
          const matched   = job.matched   || 0;
          const pct       = total > 0 ? (completed / total * 100) : 0;

          document.getElementById('progress-bar-fill').style.width = pct.toFixed(1) + '%';
          document.getElementById('progress-label').textContent = completed + ' / ' + total;
          document.getElementById('stat-progress').textContent = completed + ' / ' + total + ' scanned  ';
          document.getElementById('stat-matched').textContent = matched.toLocaleString();

          if (job.status === 'done' || job.status === 'error') {
            const elapsed = Math.round(performance.now() - t0);
            document.getElementById('stat-time').textContent = elapsed.toLocaleString();
            btn.disabled = false;
            btn.querySelector('.run-btn-text').textContent = '▶ RUN OPTIONS SCAN';

            if (job.status === 'error') {
              showState('idle');
              alert('Scan error: ' + (job.error || 'unknown error'));
              return;
            }

            const results = job.results || {};
            const expiries = Object.keys(results).sort();
            if (!expiries.length) { showState('empty'); return; }

            renderGroups(results, expiries);
            showState('table');
          } else {
            _pollTimer = setTimeout(tick, 500);
          }
        })
        .catch(err => {
          btn.disabled = false;
          btn.querySelector('.run-btn-text').textContent = '▶ RUN OPTIONS SCAN';
          showState('idle');
          alert('Poll error: ' + err.message);
        });
    }
    tick();
  }

  function renderGroups(results, expiries) {
    const container = document.getElementById('results-groups');
    container.innerHTML = '';

    expiries.forEach(function (expiry) {
      const rows = results[expiry].slice().sort((a, b) => b.score - a.score);

      const section = document.createElement('div');
      section.className = 'expiry-section';
      section.innerHTML = `
        <div class="expiry-header" onclick="this.parentElement.classList.toggle('collapsed')">
          <span class="expiry-date">EXPIRY: ${esc(expiry)}</span>
          <span class="expiry-count">${rows.length} contract${rows.length !== 1 ? 's' : ''}</span>
          <span class="expiry-toggle">▾</span>
        </div>
        <div class="expiry-body">
          <table class="results-table">
            <thead>
              <tr>
                <th>TICKER</th><th>STRIKE</th><th>DELTA</th>
                <th>BID</th><th>ASK</th><th>IV</th><th>IV PREM</th>
                <th>OI</th><th>VOLUME</th><th>DTE</th><th>SCORE</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map((r, i) => `
                <tr class="result-row" style="animation-delay:${i * 20}ms">
                  <td class="ticker-cell">${esc(r.ticker)}</td>
                  <td class="num-cell">$${r.strike.toFixed(0)}</td>
                  <td class="num-cell">${r.delta.toFixed(2)}</td>
                  <td class="num-cell accent-green">$${r.bid.toFixed(2)}</td>
                  <td class="num-cell">$${r.ask.toFixed(2)}</td>
                  <td class="num-cell">${(r.iv * 100).toFixed(1)}%</td>
                  <td class="num-cell">${r.iv_premium.toFixed(2)}x</td>
                  <td class="num-cell">${r.oi.toLocaleString()}</td>
                  <td class="num-cell">${r.volume.toLocaleString()}</td>
                  <td class="num-cell">${r.dte}</td>
                  <td class="num-cell score-cell">${r.score}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
      container.appendChild(section);
    });
  }

  showState('idle');
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Add minimal CSS for the new elements to `src/static/css/styles.css`**

Append to the end of `styles.css`:

```css
/* ── Options Scanner additions ─────────────────────────── */
.schwab-warn {
  background: rgba(255, 160, 0, 0.08);
  border: 1px solid rgba(255, 160, 0, 0.4);
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 0.78rem;
  color: #ffa000;
  margin-bottom: 16px;
}
.schwab-warn a { color: #ffa000; text-decoration: underline; }
.warn-icon { margin-right: 6px; }

.nav-links {
  display: flex;
  gap: 6px;
  margin-left: 24px;
}
.nav-link {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  color: var(--text-dim, #888);
  text-decoration: none;
  padding: 4px 10px;
  border: 1px solid transparent;
  border-radius: 3px;
  transition: color 0.2s, border-color 0.2s;
}
.nav-link:hover,
.nav-link-active {
  color: var(--accent, #00e5ff);
  border-color: var(--accent, #00e5ff);
}

.expiry-section {
  margin-bottom: 16px;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 4px;
  overflow: hidden;
}
.expiry-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  background: rgba(255,255,255,0.03);
  cursor: pointer;
  user-select: none;
}
.expiry-date { font-size: 0.8rem; letter-spacing: 0.06em; color: var(--accent, #00e5ff); }
.expiry-count { font-size: 0.72rem; color: #888; }
.expiry-toggle { margin-left: auto; font-size: 0.9rem; color: #555; transition: transform 0.2s; }
.expiry-section.collapsed .expiry-body { display: none; }
.expiry-section.collapsed .expiry-toggle { transform: rotate(-90deg); }
.expiry-body { overflow-x: auto; }

.score-cell { color: var(--accent, #00e5ff); font-weight: 600; }
.param-number-input {
  width: 100%;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 4px;
  color: inherit;
  padding: 7px 10px;
  font-size: 0.85rem;
  font-family: inherit;
  outline: none;
}
.param-number-input:focus { border-color: var(--accent, #00e5ff); }
```

- [ ] **Step 3: Start the app and manually verify the Options Scanner page**

```
flask --app src/app.py run
```

1. Visit `http://localhost:5000/options` — page loads with control panel
2. Both nav links visible in the header
3. If Schwab not connected: warning message shown, Run button disabled
4. If Schwab connected: Run button enabled

- [ ] **Step 4: Run full test suite**

```
pytest tests/ --ignore=tests/e2e -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/templates/options.html src/static/css/styles.css
git commit -m "feat(options): add Options Scanner UI page with expiry-grouped results"
```

---

## Task 8: Final integration check

- [ ] **Step 1: Run complete test suite one final time**

```
pytest tests/ --ignore=tests/e2e -v
```
Expected: all PASSED, no new failures

- [ ] **Step 2: Verify module imports are clean**

```
python -c "from src.options.result import OptionResult; from src.options.scorer import OptionScorer; from src.options.provider import SchwabOptionsProvider; from src.options.scanner import OptionsScanner; from src.options.routes import bp; print('All imports OK')"
```
Expected: `All imports OK`

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "feat(options): complete options put scanner feature"
```
