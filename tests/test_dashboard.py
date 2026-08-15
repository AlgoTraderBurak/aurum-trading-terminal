from __future__ import annotations

import pandas as pd

from aurum.domain.models import Direction, Timeframe
from aurum.service import DashboardCell
from aurum.ui.dashboard_tab import DashboardTab


def test_radar_prefers_multi_timeframe_alignment():
    now = pd.Timestamp("2026-08-12 20:30", tz="UTC")
    cells = [
        DashboardCell("XAUUSD", tf, Direction.LONG, 76, "Trend", "İŞLEM YOK", 4400, "Test", session="New York", volatility_percentile=72, asof=now)
        for tf in (Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1)
    ]
    cells += [
        DashboardCell("XAGUSD", Timeframe.M15, Direction.LONG, 65, "Geçiş", "İŞLEM YOK", 51, "Test", asof=now),
        DashboardCell("XAGUSD", Timeframe.H1, Direction.SHORT, 65, "Geçiş", "İŞLEM YOK", 51, "Test", asof=now),
        DashboardCell("XAGUSD", Timeframe.H4, Direction.NEUTRAL, 40, "Yatay", "İŞLEM YOK", 51, "Test", asof=now),
    ]

    rows = DashboardTab.build_radar_rows(cells)

    assert rows[0].symbol == "XAUUSD"
    assert rows[0].alignment == "Tam hizalı"
    assert rows[0].direction is Direction.LONG
    assert rows[0].score > rows[1].score
