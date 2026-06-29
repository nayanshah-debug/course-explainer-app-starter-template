"""
Pipeline: resolves filter names to instances, fetches universe, runs the engine.
"""
from typing import Callable, Dict, List, Any, Optional

from src.data.universe import get_dow_tickers, get_nasdaq_tickers, get_nyse_tickers, get_nasdaq_nyse_tickers, get_combined_universe, get_all_us_tickers
from src.filters import FILTER_REGISTRY
from src.scanner.engine import ScanEngine
from src.scanner.result import ScanResult


def build_filters(filter_specs: List[Dict[str, Any]]) -> List:
    """
    Build filter instances from a list of specs.

    Args:
        filter_specs: [{"name": "ema_crossover", "params": {"fast": 9, "slow": 21}}, ...]

    Returns:
        List of BaseFilter instances.

    Raises:
        ValueError if an unknown filter name is given.
    """
    filters = []
    for spec in filter_specs:
        name = spec.get("name", "")
        params = spec.get("params", {})
        cls = FILTER_REGISTRY.get(name)
        if cls is None:
            raise ValueError(f"Unknown filter: '{name}'. Available: {list(FILTER_REGISTRY)}")
        filters.append(cls(**params))
    return filters


def run_scan(
    universe_name: str,
    filter_specs: List[Dict[str, Any]],
    interval: str = "1d",
    period: str = "6mo",
    symbols: List[str] = None,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Run a full scan.

    Args:
        universe_name: "nasdaq" | "dow" | "both" | "all_us" | "symbols"
        filter_specs: list of {name, params} dicts
        interval: OHLCV bar interval
        period: lookback period
        symbols: explicit list of tickers (used when universe_name="symbols")

    Returns:
        dict with keys: results, total_scanned, matched, filters_used
    """
    if universe_name == "symbols" and symbols:
        universe = [s.strip().upper() for s in symbols if s.strip()]
    elif universe_name == "nasdaq":
        universe = get_nasdaq_tickers()
    elif universe_name == "nyse":
        universe = get_nyse_tickers()
    elif universe_name == "nasdaq_nyse":
        universe = get_nasdaq_nyse_tickers()
    elif universe_name == "dow":
        universe = get_dow_tickers()
    elif universe_name == "all_us":
        universe = get_all_us_tickers(min_price=4.0)
    else:
        universe = get_combined_universe()

    filters = build_filters(filter_specs)
    engine = ScanEngine()
    results: List[ScanResult] = engine.run(universe, filters, interval, period,
                                           progress_callback=progress_callback)

    return {
        "results": [r.to_dict() for r in results],
        "total_scanned": len(universe),
        "matched": len(results),
        "filters_used": [f.name for f in filters],
    }
