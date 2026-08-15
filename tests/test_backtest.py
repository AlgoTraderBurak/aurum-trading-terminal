from __future__ import annotations

import pandas as pd

from aurum.backtest.engine import BacktestEngine
from aurum.backtest.diagnostics import diagnose_backtest
from aurum.data.quality import validate_bars
from aurum.domain.models import (
    BacktestConfig,
    Direction,
    MarketDataBundle,
    Signal,
    SignalAction,
    SignalStage,
    SymbolMetadata,
    Timeframe,
)


def _signal(ts, bar=0):
    return Signal(
        "sig", "TEST", Timeframe.M15, ts, bar, SignalAction.BUY, SignalStage.CONFIRMED,
        Direction.LONG, 80, "Test", 100, 99, 102, 2, ("test",), (), "99 altı",
    )


def _bundle(df):
    return MarketDataBundle(
        "TEST", "TEST", Timeframe.M15, df, df, None, "Test",
        SymbolMetadata("TEST", "TEST", digits=2, point=.01, tick_size=.01, tick_value=1),
        validate_bars(df, Timeframe.M15, continuous=True, now=df.index[-1]),
        pd.Timestamp.now(tz="UTC"),
    )


def test_entry_is_next_bar_and_stop_wins_ambiguous_bar():
    idx = pd.date_range("2025-01-01", periods=60, freq="15min", tz="UTC")
    df = pd.DataFrame({"open":100., "high":100.5, "low":99.5, "close":100., "volume":100.}, index=idx)
    df.iloc[1] = [100, 103, 98, 100, 100]  # both stop and target touched
    result = BacktestEngine().run(_bundle(df), [_signal(idx[0])], BacktestConfig())
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_time == idx[1]
    assert trade.exit_reason == "Stop"
    assert trade.net_r == -1
    assert result.metrics["final_balance"] == result.config.initial_balance + trade.pnl


def test_costs_reduce_result():
    idx = pd.date_range("2025-01-01", periods=60, freq="15min", tz="UTC")
    df = pd.DataFrame({"open":100., "high":100.2, "low":99.8, "close":100., "volume":100.}, index=idx)
    df.iloc[1] = [100, 102.2, 99.8, 102, 100]
    bundle = _bundle(df)
    clean = BacktestEngine().run(bundle, [_signal(idx[0])], BacktestConfig())
    costly = BacktestEngine().run(bundle, [_signal(idx[0])], BacktestConfig(spread_points=4, slippage_points=2, commission_per_lot=1))
    assert costly.metrics["net_r"] < clean.metrics["net_r"]


def test_diagnostics_report_sample_size_and_excursions():
    idx = pd.date_range("2025-01-01", periods=60, freq="15min", tz="UTC")
    df = pd.DataFrame({"open":100., "high":100.8, "low":98.8, "close":100., "volume":100.}, index=idx)
    bundle = _bundle(df)
    signal = _signal(idx[0])
    result = BacktestEngine().run(bundle, [signal], BacktestConfig())
    snapshot = type("Snapshot", (), {"signals": [signal], "frame": df})()

    notes = diagnose_backtest(snapshot, result)

    assert any("Örneklem" in note for note in notes)
    assert any("MFE" in note and "MAE" in note for note in notes)
