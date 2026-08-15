from __future__ import annotations

import numpy as np
import pandas as pd

from aurum.analysis.indicators import compute_indicator_frame


def test_indicator_frame_has_expected_columns(bars):
    result = compute_indicator_frame(bars)
    expected = {"ema20", "ema50", "ema200", "atr", "atr_pct", "rsi", "adx", "vwap", "relative_volume"}
    assert expected.issubset(result.columns)
    assert result.index.equals(bars.index)


def test_indicators_do_not_change_past_when_future_is_appended(bars):
    prefix = bars.iloc[:320]
    first = compute_indicator_frame(prefix)
    second = compute_indicator_frame(bars)
    for column in ("ema20", "ema50", "ema200", "atr", "rsi", "adx", "vwap", "kernel"):
        np.testing.assert_allclose(
            first[column].to_numpy(), second[column].iloc[:320].to_numpy(), equal_nan=True, rtol=1e-12
        )


def test_vwap_resets_daily(bars):
    result = compute_indicator_frame(bars)
    day_starts = pd.Series(result.index.date, index=result.index).ne(pd.Series(result.index.date, index=result.index).shift())
    for ts in result.index[day_starts]:
        row = result.loc[ts]
        typical = (row.high + row.low + row.close) / 3
        assert abs(row.vwap - typical) < 1e-10
