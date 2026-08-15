from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from aurum.domain.models import SymbolMetadata, Timeframe


@dataclass(frozen=True)
class MarketFetch:
    symbol: str
    frame: pd.DataFrame
    metadata: SymbolMetadata
    source: str = "MT5"


class MarketDataClient(Protocol):
    def fetch_bars(self, requested: str, timeframe: Timeframe, count: int = 2500) -> MarketFetch: ...

    def close(self) -> None: ...
