from __future__ import annotations

import pandas as pd

from aurum.analysis.engine import AnalysisEngine
from aurum.backtest.engine import BacktestEngine
from aurum.data.quality import validate_bars
from aurum.domain.models import BacktestConfig, MarketDataBundle, SymbolMetadata, Timeframe
from aurum.reporting import ReportJournal


def _bundle(bars: pd.DataFrame) -> MarketDataBundle:
    return MarketDataBundle(
        "TEST", "TEST", Timeframe.M15, bars, bars, None, "Test",
        SymbolMetadata("TEST", "TEST", digits=2, point=.01, tick_size=.01, tick_value=1),
        validate_bars(bars, Timeframe.M15, continuous=True, now=bars.index[-1]),
        pd.Timestamp.now(tz="UTC"),
    )


def test_analysis_reports_are_deduplicated_and_notes_persist(tmp_path, bars):
    snapshot = AnalysisEngine().analyze(_bundle(bars))
    journal = ReportJournal(tmp_path / "reports.sqlite3")

    first = journal.record_analysis(snapshot)
    second = journal.record_analysis(snapshot)

    assert first == second
    assert len(journal.list_entries()) == 1
    journal.update_note(first, "New York açılışını izle", "NY, gözlem")
    entry = journal.list_entries()[0]
    assert entry.note == "New York açılışını izle"
    assert entry.tags == "NY, gözlem"
    assert entry.payload["quality"]["row_count"] == len(bars)


def test_backtest_report_contains_monetary_result(tmp_path, bars):
    bundle = _bundle(bars)
    snapshot = AnalysisEngine().analyze(bundle)
    result = BacktestEngine().run(bundle, snapshot.signals, BacktestConfig(currency="TRY"))
    journal = ReportJournal(tmp_path / "reports.sqlite3")

    journal.record_backtest(bundle, snapshot, result)

    entry = journal.list_entries()[0]
    assert entry.kind == "BACKTEST"
    assert entry.payload["config"]["currency"] == "TRY"
    assert entry.payload["metrics"]["final_balance"] == result.metrics["final_balance"]
