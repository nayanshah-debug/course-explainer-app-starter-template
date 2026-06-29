"""
Core scan engine. Runs filters against every ticker in the universe concurrently.
Calls an optional progress_callback(completed, total, result) after each ticker.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

from src.config import Config
from src.data import fetcher
from src.filters.base import BaseFilter
from src.scanner.result import ScanResult

logger = logging.getLogger(__name__)


class ScanEngine:
    def run(
        self,
        universe: List[str],
        filters: List[BaseFilter],
        interval: str = "1d",
        period: str = "6mo",
        progress_callback: Optional[Callable[[int, int, Optional[ScanResult]], None]] = None,
    ) -> List[ScanResult]:
        """
        Scan all tickers in universe, applying all filters.
        progress_callback(completed, total, result_or_None) is called after each ticker.
        Returns only tickers that pass every filter, sorted alphabetically.
        """
        results: List[ScanResult] = []
        total = len(universe)
        completed = 0

        with ThreadPoolExecutor(max_workers=Config.SCAN_CONCURRENCY) as pool:
            futures = {
                pool.submit(self._scan_ticker, ticker, filters, interval, period): ticker
                for ticker in universe
            }
            for future in as_completed(futures):
                ticker = futures[future]
                result = None
                try:
                    result = future.result()
                    if result.passed:
                        results.append(result)
                except Exception as exc:
                    logger.warning("Error scanning %s: %s", ticker, exc)

                completed += 1
                if progress_callback:
                    progress_callback(completed, total, result if (result and result.passed) else None)

        return sorted(results, key=lambda r: r.ticker)

    def _scan_ticker(
        self,
        ticker: str,
        filters: List[BaseFilter],
        interval: str,
        period: str,
    ) -> ScanResult:
        df = fetcher.get_ohlcv(ticker, interval, period)
        if df.empty or len(df) < 2:
            return ScanResult(ticker=ticker, passed=False)

        for f in filters:
            try:
                if not f.apply(df):
                    return ScanResult(ticker=ticker, passed=False)
            except Exception as exc:
                logger.warning("Filter %s failed on %s: %s", f.name, ticker, exc)
                return ScanResult(ticker=ticker, passed=False)

        close = df["close"]
        price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])
        change_pct = ((price - prev_price) / prev_price) * 100 if prev_price else 0.0
        volume = float(df["volume"].iloc[-1])
        avg_volume = float(df["volume"].iloc[-20:].mean()) if len(df) >= 20 else float(df["volume"].mean())
        rel_volume = (volume / avg_volume) if avg_volume > 0 else 0.0

        # Signal date — bar that actually triggered the match.
        # Filters may set _signal_offset (0 = last bar, 1 = one bar ago, …).
        signal_offset = max(
            (getattr(f, "_signal_offset", 0) for f in filters),
            default=0,
        )
        signal_date = df.index[-(1 + signal_offset)].strftime("%Y-%m-%d")

        return ScanResult(
            ticker=ticker,
            passed=True,
            price=price,
            change_pct=change_pct,
            volume=volume,
            avg_volume=avg_volume,
            rel_volume=rel_volume,
            signal_date=signal_date,
            matched_filters=[f.name for f in filters],
        )
