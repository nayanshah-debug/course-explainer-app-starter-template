"""Base class for all scan filters."""
from abc import ABC, abstractmethod
import pandas as pd


class BaseFilter(ABC):
    # Subclasses must define these class attributes
    name: str = ""
    description: str = ""
    # params schema: {param_name: {"type": "int"|"float", "default": value, "label": str}}
    params: dict = {}

    @abstractmethod
    def apply(self, df: pd.DataFrame) -> bool:
        """
        Evaluate the filter against a single stock's OHLCV DataFrame.

        Args:
            df: DataFrame with columns [open, high, low, close, volume], DatetimeIndex

        Returns:
            True if the stock passes this filter, False otherwise.
        """
        ...

    # PineScript helper: crossover(a, b) — a crosses above b on last bar
    @staticmethod
    def crossover(a: pd.Series, b: pd.Series) -> bool:
        return bool(a.iloc[-1] > b.iloc[-1] and a.iloc[-2] <= b.iloc[-2])

    # PineScript helper: crossunder(a, b) — a crosses below b on last bar
    @staticmethod
    def crossunder(a: pd.Series, b: pd.Series) -> bool:
        return bool(a.iloc[-1] < b.iloc[-1] and a.iloc[-2] >= b.iloc[-2])
