from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from aurum.analysis.engine import AnalysisEngine
from aurum.backtest.engine import BacktestEngine
from aurum.backtest.diagnostics import diagnose_backtest
from aurum.data.service import DataService
from aurum.domain.models import (
    AnalysisSnapshot,
    BacktestConfig,
    BacktestResult,
    Direction,
    MarketDataBundle,
    Timeframe,
)
from aurum.reporting import JournalEntry, ReportJournal


@dataclass(frozen=True)
class DashboardCell:
    symbol: str
    timeframe: Timeframe
    direction: Direction
    score: int
    regime: str
    signal: str
    price: float
    source: str
    error: str = ""
    session: str = ""
    volatility_percentile: float | None = None
    asof: pd.Timestamp | None = None


class AurumService:
    def __init__(self, root: str | Path) -> None:
        root = Path(root)
        self.data = DataService(root / "data")
        self.analysis = AnalysisEngine()
        self.backtest_engine = BacktestEngine()
        self.reports = ReportJournal(root / "data" / "aurum_reports.sqlite3")

    def analyze(self, symbol: str, timeframe: Timeframe | str, count: int = 2500) -> tuple[MarketDataBundle, AnalysisSnapshot]:
        bundle = self.data.fetch(symbol, timeframe, count=count)
        return bundle, self.analysis.analyze(bundle)

    def multi_timeframe(
        self,
        symbol: str,
        timeframes: Iterable[Timeframe],
        count: int = 1200,
    ) -> dict[Timeframe, AnalysisSnapshot]:
        result: dict[Timeframe, AnalysisSnapshot] = {}
        for timeframe in timeframes:
            _, snapshot = self.analyze(symbol, timeframe, count)
            result[timeframe] = snapshot
        return result

    def dashboard(
        self,
        symbols: Iterable[str],
        timeframes: Iterable[Timeframe],
        count: int = 900,
    ) -> list[DashboardCell]:
        cells: list[DashboardCell] = []
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    _, snapshot = self.analyze(symbol, timeframe, count)
                    latest = snapshot.latest_signal
                    signal_age = (
                        (snapshot.asof - latest.timestamp).total_seconds() / timeframe.seconds
                        if latest is not None else float("inf")
                    )
                    signal = latest.action.tr if latest is not None and signal_age <= 8 else "İŞLEM YOK"
                    cells.append(
                        DashboardCell(
                            symbol=symbol,
                            timeframe=timeframe,
                            direction=snapshot.direction,
                            score=snapshot.score,
                            regime=snapshot.regime,
                            signal=signal,
                            price=snapshot.price,
                            source=snapshot.source,
                            session=str(snapshot.metrics.get("Seans", "")),
                            volatility_percentile=(
                                float(snapshot.metrics["ATR Yüzdesi"])
                                if snapshot.metrics.get("ATR Yüzdesi") is not None else None
                            ),
                            asof=snapshot.asof,
                        )
                    )
                except Exception as exc:
                    cells.append(
                        DashboardCell(
                            symbol=symbol,
                            timeframe=timeframe,
                            direction=Direction.NEUTRAL,
                            score=0,
                            regime="Veri yok",
                            signal="—",
                            price=0.0,
                            source="",
                            error=str(exc),
                        )
                    )
        return cells

    def backtest(
        self,
        bundle: MarketDataBundle,
        snapshot: AnalysisSnapshot,
        config: BacktestConfig,
    ) -> BacktestResult:
        result = self.backtest_engine.run(bundle, snapshot.signals, config)
        result.diagnostics = diagnose_backtest(snapshot, result)
        self.reports.record_backtest(bundle, snapshot, result)
        return result

    def record_analysis(self, snapshot: AnalysisSnapshot) -> int:
        return self.reports.record_analysis(snapshot)

    def list_reports(self, limit: int = 500) -> list[JournalEntry]:
        return self.reports.list_entries(limit=limit)

    def update_report_note(self, entry_id: int, note: str, tags: str = "") -> None:
        self.reports.update_note(entry_id, note, tags)

    def close(self) -> None:
        self.data.close()
