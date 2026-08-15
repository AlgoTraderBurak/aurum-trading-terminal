from __future__ import annotations

import pandas as pd

from aurum.data.mt5_client import MT5Error, MT5Fetch
from aurum.data.service import DataService
from aurum.domain.models import SymbolMetadata, Timeframe


class FakeClient:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.fail = False

    def fetch_bars(self, requested, timeframe, count):
        if self.fail:
            raise MT5Error("test bağlantı hatası")
        return MT5Fetch(
            requested,
            self.frame.tail(count),
            SymbolMetadata(requested, requested, digits=2, point=0.01, tick_size=0.01),
        )

    def close(self):
        return None


def test_service_excludes_open_bar_and_falls_back_to_cache(tmp_path, bars):
    now = pd.Timestamp.now(tz="UTC").floor("15min") + pd.Timedelta(minutes=5)
    dynamic = bars.copy()
    dynamic.index = pd.date_range(end=now.floor("15min"), periods=len(dynamic), freq="15min", tz="UTC")
    client = FakeClient(dynamic)
    service = DataService(tmp_path, client=client)
    first = service.fetch("TEST", Timeframe.M15, count=len(dynamic))
    assert first.source == "MT5"
    assert first.current_bar is not None
    assert len(first.closed_bars) == len(dynamic) - 1

    client.fail = True
    cached = service.fetch("TEST", Timeframe.M15, count=len(dynamic))
    assert cached.source.startswith("Önbellek")
    assert cached.current_bar is None
    assert cached.closed_bars.index[-1] == dynamic.index[-2]
