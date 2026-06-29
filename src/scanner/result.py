from dataclasses import dataclass, field
from typing import List


@dataclass
class ScanResult:
    ticker: str
    passed: bool
    price: float = 0.0
    change_pct: float = 0.0
    volume: float = 0.0
    avg_volume: float = 0.0        # 20-bar average volume
    rel_volume: float = 0.0        # volume / avg_volume
    signal_date: str = ""          # date/time of the bar that triggered the signal
    matched_filters: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": round(self.price, 2),
            "change_pct": round(self.change_pct, 2),
            "volume": int(self.volume),
            "avg_volume": int(self.avg_volume),
            "rel_volume": round(self.rel_volume, 2),
            "signal_date": self.signal_date,
            "matched_filters": self.matched_filters,
        }
