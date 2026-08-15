from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from aurum.domain.models import AnalysisSnapshot, Direction, SignalAction
from aurum.ui.theme import AMBER, GREEN, RED
from aurum.ui.report_journal import ReportJournalWidget
from aurum.ui.widgets import MetricCard


class AnalysisTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        header = QLabel("Analiz / Yorum / Sinyal")
        header.setObjectName("sectionTitle")
        root.addWidget(header)
        cards = QHBoxLayout()
        self.bias = MetricCard("Birleşik Yön")
        self.regime = MetricCard("Rejim")
        self.asof = MetricCard("Son Kapanmış Mum")
        self.quality = MetricCard("Veri Güveni")
        for x in (self.bias, self.regime, self.asof, self.quality):
            cards.addWidget(x)
        root.addLayout(cards)

        sections = QTabWidget()
        live_page = QWidget()
        live_layout = QVBoxLayout(live_page)
        live_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Türkçe piyasa yorumu"))
        self.commentary = QTextBrowser()
        left_layout.addWidget(self.commentary, 2)
        left_layout.addWidget(QLabel("Hesaplama özeti"))
        self.metrics = QTableWidget(0, 2)
        self.metrics.setHorizontalHeaderLabels(["Parametre", "Değer"])
        self.metrics.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.metrics.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.metrics.verticalHeader().setVisible(False)
        left_layout.addWidget(self.metrics, 3)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Sinyal geçmişi ve izlenebilirlik"))
        self.signals = QTableWidget(0, 7)
        self.signals.setHorizontalHeaderLabels(["Zaman", "Karar", "Puan", "Kurulum", "Giriş", "Stop", "Hedef"])
        self.signals.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.signals.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.signals.verticalHeader().setVisible(False)
        self.signals.setAlternatingRowColors(True)
        right_layout.addWidget(self.signals, 3)
        right_layout.addWidget(QLabel("Seçili sinyal gerekçesi"))
        self.signal_detail = QTextBrowser()
        right_layout.addWidget(self.signal_detail, 2)
        splitter.addWidget(right)
        splitter.setSizes([480, 720])
        live_layout.addWidget(splitter)
        sections.addTab(live_page, "Güncel Analiz")
        self.journal = ReportJournalWidget()
        sections.addTab(self.journal, "Rapor Defteri")
        root.addWidget(sections, 1)
        self.signals.itemSelectionChanged.connect(self._show_selected_signal)
        self._snapshot: AnalysisSnapshot | None = None

    @staticmethod
    def _format(value) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:,.4f}"
        return str(value)

    def set_snapshot(self, snapshot: AnalysisSnapshot) -> None:
        self._snapshot = snapshot
        color = GREEN if snapshot.direction is Direction.LONG else RED if snapshot.direction is Direction.SHORT else AMBER
        self.bias.set_value(f"{snapshot.direction.tr} · {snapshot.score}/100", color)
        self.regime.set_value(snapshot.regime)
        self.asof.set_value(snapshot.asof.strftime("%d.%m.%Y %H:%M UTC"))
        self.quality.set_value(snapshot.quality.status_tr, GREEN if snapshot.quality.status_tr == "SAĞLIKLI" else AMBER)

        latest = snapshot.latest_signal
        signal_html = "<p><b>Yeni bir işlem sinyali yok.</b> Bu, sistemin hata verdiği değil şartların birleşmediği anlamına gelir.</p>"
        if latest:
            warn = "" if not latest.warnings else "<p style='color:#f3b33d'><b>Uyarı:</b> " + "; ".join(latest.warnings) + "</p>"
            signal_html = (
                f"<p><b>Son durum:</b> {latest.action.tr} · {latest.score}/100 · {latest.setup}</p>"
                f"<p><b>Zaman:</b> {latest.timestamp:%d.%m.%Y %H:%M} UTC · "
                f"<b>R:R:</b> {self._format(latest.rr)}</p>{warn}"
            )
        issues = "".join(f"<li>{x.message}</li>" for x in snapshot.quality.issues)
        self.commentary.setHtml(
            f"<h3>{snapshot.symbol} / {snapshot.timeframe.label}</h3>"
            f"<p>{snapshot.narrative}</p>{signal_html}"
            f"<p><b>Kaynak:</b> {snapshot.source}</p>"
            + (f"<p><b>Veri notları:</b></p><ul>{issues}</ul>" if issues else "")
        )

        self.metrics.setRowCount(len(snapshot.metrics))
        for row, (name, value) in enumerate(snapshot.metrics.items()):
            self.metrics.setItem(row, 0, QTableWidgetItem(name))
            self.metrics.setItem(row, 1, QTableWidgetItem(self._format(value)))

        recent = list(reversed(snapshot.signals[-250:]))
        self.signals.setRowCount(len(recent))
        for row, signal in enumerate(recent):
            values = (
                signal.timestamp.strftime("%d.%m.%Y %H:%M"), signal.action.tr,
                str(signal.score), signal.setup, self._format(signal.entry),
                self._format(signal.stop), self._format(signal.target),
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, signal.uid)
                if col == 1:
                    item.setForeground(QColor(GREEN if signal.action is SignalAction.BUY else RED if signal.action is SignalAction.SELL else AMBER))
                self.signals.setItem(row, col, item)
        if recent:
            self.signals.selectRow(0)
        else:
            self.signal_detail.setText("Sinyal geçmişi yok.")

    def _show_selected_signal(self) -> None:
        if self._snapshot is None:
            return
        row = self.signals.currentRow()
        item = self.signals.item(row, 0) if row >= 0 else None
        uid = item.data(Qt.UserRole) if item else None
        signal = next((x for x in self._snapshot.signals if x.uid == uid), None)
        if signal is None:
            return
        reasons = "".join(f"<li>{x}</li>" for x in signal.reasons)
        warnings = "".join(f"<li>{x}</li>" for x in signal.warnings)
        self.signal_detail.setHtml(
            f"<p><b>{signal.action.tr} · {signal.setup} · {signal.score}/100</b></p>"
            f"<p><b>Geçersizlik:</b> {signal.invalidation}</p>"
            f"<p><b>Gerekçeler</b></p><ul>{reasons}</ul>"
            + (f"<p style='color:#f3b33d'><b>Uyarılar</b></p><ul>{warnings}</ul>" if warnings else "")
        )
