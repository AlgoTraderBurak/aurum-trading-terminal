from __future__ import annotations

import numpy as np
import pandas as pd

from aurum.data.quality import split_closed_bars, validate_bars
from aurum.domain.models import Timeframe


def test_valid_bars_are_signal_safe(bars):
    report = validate_bars(bars, Timeframe.M15, continuous=True, now=bars.index[-1])
    assert report.valid_for_signals
    assert report.ohlc_violations == 0


def test_current_bar_is_separated(bars):
    now = bars.index[-1] + pd.Timedelta(minutes=5)
    closed, current = split_closed_bars(bars, Timeframe.M15, now)
    assert len(closed) == len(bars) - 1
    assert current is not None
    assert current.name == bars.index[-1]


def test_nan_is_critical(bars):
    broken = bars.copy()
    broken.iloc[20, broken.columns.get_loc("close")] = np.nan
    report = validate_bars(broken, Timeframe.M15, continuous=True, now=bars.index[-1])
    assert not report.valid_for_signals
    assert report.nan_rows == 1


def test_duplicate_is_critical(bars):
    broken = pd.concat([bars, bars.iloc[[-1]]])
    report = validate_bars(broken, Timeframe.M15, continuous=True, now=bars.index[-1])
    assert not report.valid_for_signals
    assert report.duplicate_bars == 1


def test_non_monotonic_is_not_silently_sorted(bars):
    broken = bars.iloc[[1, 0, *range(2, len(bars))]]
    report = validate_bars(broken, Timeframe.M15, continuous=True, now=bars.index[-1])
    assert not report.valid_for_signals
    assert not report.monotonic
