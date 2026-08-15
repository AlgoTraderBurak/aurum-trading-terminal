from __future__ import annotations

from aurum.data.cache import BarCache
from aurum.domain.models import Timeframe


def test_cache_round_trip(tmp_path, bars):
    cache = BarCache(tmp_path / "bars.sqlite3")
    assert cache.store("TEST", Timeframe.M15, bars) == len(bars)
    loaded = cache.load("TEST", Timeframe.M15, 100)
    assert len(loaded) == 100
    assert loaded.index[-1] == bars.index[-1]
    assert loaded.iloc[-1].close == bars.iloc[-1].close


def test_mt5_client_exposes_no_order_api():
    from aurum.data.mt5_client import MT5ReadOnlyClient

    assert not hasattr(MT5ReadOnlyClient, "order_send")
    assert not hasattr(MT5ReadOnlyClient, "order_check")
