"""
Filter registry with auto-discovery of pinescript_converted/ modules.
Any class in filters/pinescript_converted/ that subclasses BaseFilter
is automatically registered — no manual edit needed.
"""
import importlib
import inspect
import pkgutil
import logging
from typing import Dict, Type

from src.filters.base import BaseFilter

logger = logging.getLogger(__name__)

# Built-in filters
from src.filters.ema_crossover import EMACrossoverFilter
from src.filters.rsi_oversold import RSIOversoldFilter
from src.filters.rsi_overbought import RSIOverboughtFilter
from src.filters.volume_surge import VolumeSurgeFilter
from src.filters.relative_volume import RelativeVolumeFilter
from src.filters.macd_crossover import MACDCrossoverFilter
from src.filters.above_ema import AboveEMAFilter

FILTER_REGISTRY: Dict[str, Type[BaseFilter]] = {
    EMACrossoverFilter.name: EMACrossoverFilter,
    RSIOversoldFilter.name: RSIOversoldFilter,
    RSIOverboughtFilter.name: RSIOverboughtFilter,
    VolumeSurgeFilter.name: VolumeSurgeFilter,
    RelativeVolumeFilter.name: RelativeVolumeFilter,
    MACDCrossoverFilter.name: MACDCrossoverFilter,
    AboveEMAFilter.name: AboveEMAFilter,
}


def _autodiscover_pinescript_filters() -> None:
    """Scan pinescript_converted/ and register any BaseFilter subclasses."""
    import src.filters.pinescript_converted as pkg
    for finder, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        full_name = f"src.filters.pinescript_converted.{module_name}"
        try:
            module = importlib.import_module(full_name)
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(cls, BaseFilter)
                    and cls is not BaseFilter
                    and cls.name
                    and cls.name not in FILTER_REGISTRY
                ):
                    FILTER_REGISTRY[cls.name] = cls
                    logger.info("Registered PineScript filter: %s", cls.name)
        except Exception as exc:
            logger.warning("Failed to load filter module %s: %s", full_name, exc)


_autodiscover_pinescript_filters()
