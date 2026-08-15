from __future__ import annotations

import pandas as pd

from aurum.analysis.indicators import compute_indicator_frame
from aurum.analysis.structure import analyze_structure
from aurum.domain.models import ZoneKind


def test_pivot_events_respect_confirmation_delay(bars):
    result = analyze_structure(compute_indicator_frame(bars), pivot_left=3, pivot_right=2)
    for event in result.events:
        if event.kind.startswith(("BOS", "CHOCH")):
            assert event.bar >= event.source_bar + 2


def test_fvg_cannot_touch_on_birth_bar():
    idx = pd.date_range("2025-01-01", periods=8, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100, 100, 102, 104, 104, 103, 102, 101],
            "high": [101, 101, 103, 105, 105, 104, 103, 102],
            "low": [99, 99, 102, 103, 103, 101, 100, 99],
            "close": [100, 100, 102.5, 104, 104, 102, 101, 100],
            "volume": [100] * 8,
        },
        index=idx,
        dtype=float,
    )
    features = compute_indicator_frame(df)
    features["atr"] = 1.0
    result = analyze_structure(features, fvg_atr=0.1)
    fvgs = [z for z in result.zones if z.kind is ZoneKind.FVG]
    assert fvgs
    assert all(z.touched_at is None or z.touched_at > z.born_at for z in fvgs)


def test_structure_prefix_is_stable(bars):
    short = analyze_structure(compute_indicator_frame(bars.iloc[:320]))
    full = analyze_structure(compute_indicator_frame(bars))
    short_events = [(x.kind, x.timestamp, x.level) for x in short.events]
    full_prefix = [(x.kind, x.timestamp, x.level) for x in full.events if x.timestamp <= bars.index[319]]
    assert short_events == full_prefix
