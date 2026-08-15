from __future__ import annotations

import pandas as pd

from aurum.analysis.engine import AnalysisEngine
from aurum.data.quality import validate_bars
from aurum.domain.models import MarketDataBundle, SignalStage, SymbolMetadata, Timeframe


def _bundle(bars):
    quality = validate_bars(bars, Timeframe.M15, continuous=True, now=bars.index[-1])
    return MarketDataBundle(
        "TEST", "TEST", Timeframe.M15, bars, bars, None, "Test",
        SymbolMetadata("TEST", "TEST", digits=2, point=0.01, tick_size=0.01),
        quality, pd.Timestamp.now(tz="UTC"),
    )


def test_analysis_is_deterministic(bars):
    engine = AnalysisEngine()
    first = engine.analyze(_bundle(bars))
    second = engine.analyze(_bundle(bars))
    assert first.score == second.score
    assert [x.to_dict() for x in first.signals] == [x.to_dict() for x in second.signals]


def test_signal_ids_are_unique_and_on_closed_bars(bars):
    result = AnalysisEngine().analyze(_bundle(bars))
    ids = [x.uid for x in result.signals]
    assert len(ids) == len(set(ids))
    assert all(x.timestamp in bars.index for x in result.signals)
    assert all(x.bar < len(bars) for x in result.signals)


def test_confirmed_signals_have_risk_geometry(bars):
    result = AnalysisEngine().analyze(_bundle(bars))
    for signal in result.signals:
        if signal.stage is not SignalStage.CONFIRMED:
            continue
        assert signal.entry is not None and signal.stop is not None and signal.target is not None
        assert signal.rr is not None and signal.rr >= 1.5
        if signal.direction.value > 0:
            assert signal.stop < signal.entry < signal.target
        else:
            assert signal.stop > signal.entry > signal.target


def test_analysis_derives_higher_timeframe_context(bars):
    result = AnalysisEngine().analyze(_bundle(bars))

    assert "H1" in result.mtf_context
    assert result.mtf_context["H1"]["bars"] >= 50
    assert result.mtf_context["H1"]["derived"] is True


def test_past_signals_do_not_change_when_future_bars_arrive(bars):
    engine = AnalysisEngine()
    prefix = bars.iloc[:360]
    first = engine.analyze(_bundle(prefix))
    second = engine.analyze(_bundle(bars))
    cutoff = prefix.index[-1]
    assert [x.to_dict() for x in first.signals] == [
        x.to_dict() for x in second.signals if x.timestamp <= cutoff
    ]
