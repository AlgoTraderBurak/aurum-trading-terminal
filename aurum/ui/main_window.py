from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, QThreadPool, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from aurum.domain.models import BacktestConfig, Timeframe
from aurum.service import AurumService
from aurum.ui.analysis_tab import AnalysisTab
from aurum.ui.backtest_tab import BacktestTab
from aurum.ui.dashboard_tab import DashboardTab
from aurum.ui.live_tab import LiveTab
from aurum.ui.worker import FunctionWorker


class MainWindow(QMainWindow):
    def __init__(self, root: str | Path) -> None:
        super().__init__()
        self.root = Path(root)
        self.service = AurumService(self.root)
        self.pool = QThreadPool.globalInstance()
        self.settings = QSettings("AURUM", "PiyasaTerminali")
        self.logger = logging.getLogger("aurum.ui")
        self._workers: list[FunctionWorker] = []
        self._live_busy = False
        self._dashboard_busy = False
        self._backtest_busy = False
        self._closing = False
        self._bundle = None
        self._snapshot = None

        self.setWindowTitle("AURUM · Piyasa Okuma, Sinyal ve Backtest Terminali")
        self.resize(1540, 960)
        self.setMinimumSize(1120, 720)
        tabs = QTabWidget()
        self.tabs = tabs
        self.live = LiveTab()
        self.analysis = AnalysisTab()
        self.dashboard = DashboardTab()
        self.backtest = BacktestTab()
        tabs.addTab(self.live, "Canlı Grafik")
        tabs.addTab(self.analysis, "Analiz / Yorum / Sinyal")
        tabs.addTab(self.dashboard, "Dashboard")
        tabs.addTab(self.backtest, "Backtest")
        self.setCentralWidget(tabs)
        self.statusBar().showMessage("AURUM hazırlanıyor…")

        saved_symbol = self.settings.value("symbol", "XAUUSD")
        saved_tf = self.settings.value("timeframe", "M15")
        self.live.symbol.setCurrentText(str(saved_symbol))
        self.live.timeframe.setCurrentText(str(saved_tf))
        self._restore_ui_state()

        self.live.refresh_requested.connect(lambda: self.refresh_live(full=True))
        self.live.selection_changed.connect(self._selection_changed)
        self.dashboard.refresh_requested.connect(self.refresh_dashboard)
        self.dashboard.open_requested.connect(self._open_from_dashboard)
        self.analysis.journal.refresh_requested.connect(self.refresh_journal)
        self.analysis.journal.note_requested.connect(self._save_report_note)
        self.backtest.run_requested.connect(self.run_backtest)
        self.dashboard.symbols.textChanged.connect(lambda value: self.settings.setValue("dashboard/symbols", value))
        for name, box in self.live.layer_checks.items():
            box.toggled.connect(lambda value, key=name: self.settings.setValue(f"chart/{key}", value))
        self.live.extra_indicator.currentIndexChanged.connect(
            lambda value: self.settings.setValue("chart/extra_indicator", value)
        )
        self.backtest.balance.valueChanged.connect(lambda value: self.settings.setValue("backtest/balance", value))
        self.backtest.risk.valueChanged.connect(lambda value: self.settings.setValue("backtest/risk", value))
        self.backtest.currency.currentTextChanged.connect(lambda value: self.settings.setValue("backtest/currency", value))
        self.tabs.currentChanged.connect(lambda value: self.settings.setValue("ui/tab", value))
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.refresh_live(full=False))
        self.timer.start(self._refresh_interval(Timeframe.parse(str(saved_tf))))
        QTimer.singleShot(150, lambda: self.refresh_live(full=True))
        QTimer.singleShot(250, self.refresh_journal)
        self.logger.info("AURUM arayüzü başlatıldı")

    def _restore_ui_state(self) -> None:
        self.dashboard.symbols.setText(
            str(self.settings.value("dashboard/symbols", self.dashboard.symbols.text()))
        )
        for name, box in self.live.layer_checks.items():
            value = self.settings.value(f"chart/{name}", box.isChecked(), type=bool)
            box.setChecked(bool(value))
        self.live.extra_indicator.setCurrentIndex(
            int(self.settings.value("chart/extra_indicator", 0))
        )
        self.backtest.balance.setValue(
            float(self.settings.value("backtest/balance", self.backtest.balance.value()))
        )
        self.backtest.risk.setValue(
            float(self.settings.value("backtest/risk", self.backtest.risk.value()))
        )
        self.backtest.currency.setCurrentText(
            str(self.settings.value("backtest/currency", self.backtest.currency.currentText()))
        )
        tab_index = max(0, min(self.tabs.count() - 1, int(self.settings.value("ui/tab", 0))))
        self.tabs.setCurrentIndex(tab_index)

    @staticmethod
    def _refresh_interval(timeframe: Timeframe) -> int:
        return {
            Timeframe.M1: 3_000,
            Timeframe.M5: 4_000,
            Timeframe.M15: 6_000,
            Timeframe.H1: 15_000,
            Timeframe.H4: 30_000,
            Timeframe.D1: 60_000,
        }[timeframe]

    def _start_worker(self, worker: FunctionWorker) -> None:
        self._workers.append(worker)
        worker.signals.finished.connect(lambda w=worker: self._release_worker(w))
        self.pool.start(worker)

    def _release_worker(self, worker: FunctionWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    def _selection_changed(self, symbol: str, timeframe: str) -> None:
        if not symbol:
            return
        self.settings.setValue("symbol", symbol)
        self.settings.setValue("timeframe", timeframe)
        self.timer.setInterval(self._refresh_interval(Timeframe.parse(timeframe)))
        self.refresh_live(full=True)

    def refresh_live(self, *, full: bool) -> None:
        if self._live_busy:
            return
        symbol, timeframe = self.live.current_selection()
        if not symbol:
            self.live.set_error("Sembol boş bırakılamaz.")
            return
        self._live_busy = True
        self.live.set_loading(True)
        self.statusBar().showMessage(f"{symbol} {timeframe.label} piyasa verisi okunuyor…")
        count = 2500 if full else 700
        worker = FunctionWorker(self.service.analyze, symbol, timeframe, count)
        worker.signals.result.connect(self._live_result)
        worker.signals.error.connect(self._live_error)
        worker.signals.finished.connect(self._live_finished)
        self._start_worker(worker)

    def _live_result(self, result) -> None:
        bundle, snapshot = result
        requested, timeframe = self.live.current_selection()
        if bundle.requested_symbol.upper() != requested.upper() or bundle.timeframe is not timeframe:
            return
        self._bundle, self._snapshot = bundle, snapshot
        self.live.set_snapshot(bundle, snapshot)
        self.analysis.set_snapshot(snapshot)
        report_error = ""
        try:
            self.service.record_analysis(snapshot)
            self.refresh_journal()
        except Exception as exc:
            report_error = f" · rapor kaydı başarısız: {exc}"
            self.logger.exception("Analiz raporu kaydedilemedi")
        self.backtest.set_context(
            f"{bundle.symbol} · {bundle.timeframe.label} · {len(bundle.closed_bars):,} kapanmış mum · {bundle.source}"
        )
        self.statusBar().showMessage(
            f"{bundle.symbol} {bundle.timeframe.label} güncellendi · {snapshot.asof:%d.%m.%Y %H:%M} UTC{report_error}"
        )
        self.logger.info(
            "%s %s güncellendi; kaynak=%s, kapanmış_mum=%s, yön=%s, puan=%s",
            bundle.symbol, bundle.timeframe.label, bundle.source,
            len(bundle.closed_bars), snapshot.direction.tr, snapshot.score,
        )

    def _live_error(self, message: str) -> None:
        self.live.set_error(message)
        self.statusBar().showMessage(message.splitlines()[0])
        self.logger.error("Canlı veri/analiz hatası: %s", message.splitlines()[0])

    def _live_finished(self) -> None:
        self._live_busy = False
        self.live.set_loading(False)

    def refresh_dashboard(self, symbols: list[str]) -> None:
        if self._dashboard_busy or not symbols:
            return
        self._dashboard_busy = True
        self.dashboard.set_loading(True)
        worker = FunctionWorker(self.service.dashboard, symbols, list(Timeframe), 900)
        worker.signals.result.connect(self.dashboard.set_cells)
        worker.signals.error.connect(self.dashboard.set_error)
        worker.signals.finished.connect(self._dashboard_finished)
        self._start_worker(worker)

    def _open_from_dashboard(self, symbol: str, timeframe: str) -> None:
        self.live.symbol.setCurrentText(symbol)
        self.live.timeframe.setCurrentText(timeframe)
        self.tabs.setCurrentWidget(self.live)
        self._selection_changed(symbol, timeframe)

    def _dashboard_finished(self) -> None:
        self._dashboard_busy = False
        self.dashboard.set_loading(False)

    def run_backtest(self, config: BacktestConfig) -> None:
        if self._backtest_busy:
            return
        if self._bundle is None or self._snapshot is None:
            self.backtest.set_error("Önce canlı grafikten veri yüklenmelidir.")
            return
        self._backtest_busy = True
        self.backtest.set_loading(True)
        worker = FunctionWorker(self.service.backtest, self._bundle, self._snapshot, config)
        worker.signals.result.connect(self._backtest_result)
        worker.signals.error.connect(self.backtest.set_error)
        worker.signals.finished.connect(self._backtest_finished)
        self._start_worker(worker)

    def _backtest_finished(self) -> None:
        self._backtest_busy = False
        self.backtest.set_loading(False)

    def _backtest_result(self, result) -> None:
        self.backtest.set_result(result)
        self.refresh_journal()
        self.logger.info(
            "Backtest tamamlandı; işlem=%s, net_r=%.2f, son_bakiye=%.2f",
            int(result.metrics["trade_count"]), result.metrics["net_r"], result.metrics["final_balance"],
        )

    def refresh_journal(self) -> None:
        try:
            self.analysis.journal.set_entries(self.service.list_reports())
        except Exception as exc:
            self.statusBar().showMessage(f"Rapor Defteri okunamadı: {exc}")

    def _save_report_note(self, entry_id: int, note: str, tags: str) -> None:
        try:
            self.service.update_report_note(entry_id, note, tags)
            self.refresh_journal()
            self.analysis.journal.set_note_saved()
        except Exception as exc:
            self.statusBar().showMessage(f"Rapor notu kaydedilemedi: {exc}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        self.timer.stop()
        self.settings.sync()
        self.service.close()
        self.pool.waitForDone(3000)
        self.logger.info("AURUM kapatıldı")
        event.accept()
