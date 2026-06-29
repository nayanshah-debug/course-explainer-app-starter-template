"""
Provides ticker universes for the scanner.

Sources (all free, no API key required):
  Stocks — NASDAQ Screener API (NASDAQ, NYSE, AMEX exchanges)
  ETFs   — NASDAQ ETF Screener API
  DOW 30 — hardcoded (stable 30-component index)

All "All US" tickers are pre-filtered to price >= min_price (default $4).
"""
import logging
from functools import lru_cache
from typing import List

import requests

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_SCREENER_URL = (
    "https://api.nasdaq.com/api/screener/stocks"
    "?tableonly=true&limit=10000&offset=0&exchange={exchange}"
)
_ETF_URL = "https://api.nasdaq.com/api/screener/etf?tableonly=true&limit=10000&offset=0"

# DOW JONES 30 components (as of 2025)
_DOW_TICKERS = [
    "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
    "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
    "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WBA", "WMT",
]

# Fallback for CI / offline environments
_FALLBACK = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO",
    "COST", "NFLX", "AMD", "ADBE", "QCOM", "INTC", "INTU", "AMAT", "MU",
    "JPM", "GS", "BAC", "WMT", "HD", "PG", "JNJ", "UNH",
]


def _parse_price(raw: str) -> float:
    """Convert '$182.46' → 182.46, returns 0.0 on failure."""
    try:
        return float(raw.replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _fetch_exchange(exchange: str) -> List[dict]:
    """Fetch all rows for one exchange from the NASDAQ screener."""
    url = _SCREENER_URL.format(exchange=exchange)
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", {}).get("table", {}).get("rows", []) or []


def _fetch_etfs() -> List[dict]:
    """Fetch ETF rows from the NASDAQ ETF screener."""
    resp = requests.get(_ETF_URL, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return (
        resp.json()
        .get("data", {})
        .get("records", {})
        .get("data", {})
        .get("rows", [])
        or []
    )


@lru_cache(maxsize=1)
def get_dow_tickers() -> List[str]:
    return list(_DOW_TICKERS)


@lru_cache(maxsize=1)
def get_nasdaq_tickers() -> List[str]:
    """All NASDAQ-listed stocks, no price filter."""
    try:
        rows = _fetch_exchange("NASDAQ")
        tickers = [
            r["symbol"].strip()
            for r in rows
            if r.get("symbol") and "/" not in r["symbol"]
        ]
        logger.info("Loaded %d NASDAQ tickers", len(tickers))
        return tickers
    except Exception as exc:
        logger.warning("NASDAQ fetch failed: %s — using fallback", exc)
        return list(_FALLBACK)


@lru_cache(maxsize=1)
def get_nyse_tickers() -> List[str]:
    """All NYSE-listed stocks, no price filter."""
    try:
        rows = _fetch_exchange("NYSE")
        tickers = [
            r["symbol"].strip()
            for r in rows
            if r.get("symbol") and "/" not in r["symbol"]
        ]
        logger.info("Loaded %d NYSE tickers", len(tickers))
        return tickers
    except Exception as exc:
        logger.warning("NYSE fetch failed: %s — using fallback", exc)
        return list(_FALLBACK)


@lru_cache(maxsize=1)
def get_all_us_tickers(min_price: float = 4.0) -> List[str]:
    """
    All US-traded stocks (NASDAQ + NYSE + AMEX) and ETFs priced >= min_price.
    Returns ~5,000–5,500 tickers depending on market conditions.
    """
    tickers = []
    errors = []

    # Stocks across all three exchanges
    for exchange in ("NASDAQ", "NYSE", "AMEX"):
        try:
            rows = _fetch_exchange(exchange)
            exchange_tickers = [
                r["symbol"].strip()
                for r in rows
                if r.get("symbol")
                and "/" not in r["symbol"]
                and _parse_price(r.get("lastsale", "0")) >= min_price
            ]
            logger.info("%s: %d tickers at $%.2f+", exchange, len(exchange_tickers), min_price)
            tickers.extend(exchange_tickers)
        except Exception as exc:
            errors.append(f"{exchange}: {exc}")
            logger.warning("Failed to fetch %s: %s", exchange, exc)

    # ETFs
    try:
        etf_rows = _fetch_etfs()
        etf_tickers = [
            r["symbol"].strip()
            for r in etf_rows
            if r.get("symbol")
            and _parse_price(r.get("lastSalePrice", "0")) >= min_price
        ]
        logger.info("ETFs: %d tickers at $%.2f+", len(etf_tickers), min_price)
        tickers.extend(etf_tickers)
    except Exception as exc:
        errors.append(f"ETF: {exc}")
        logger.warning("Failed to fetch ETFs: %s", exc)

    if not tickers:
        logger.error("All universe fetches failed (%s) — using fallback", errors)
        return list(_FALLBACK)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    logger.info("All US universe: %d total tickers at $%.2f+", len(unique), min_price)
    return unique


def get_nasdaq_nyse_tickers() -> List[str]:
    """NASDAQ + NYSE deduplicated."""
    return list(dict.fromkeys(get_nasdaq_tickers() + get_nyse_tickers()))


def get_combined_universe() -> List[str]:
    """NASDAQ + DOW deduplicated (backward compat)."""
    return list(dict.fromkeys(get_nasdaq_tickers() + get_dow_tickers()))
