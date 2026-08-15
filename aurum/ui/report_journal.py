from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from aurum.reporting import JournalEntry
from aurum.ui.theme import AMBER, BLUE, GREEN, RED


class ReportJournalWidget(QWidget):
    refresh_requested = Signal()
    note_requested = Signal(int, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[JournalEntry] = []
        self._visible: list[JournalEntry] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        tools = QHBoxLayout()
        tools.addWidget(QLabel("Kayıt türü"))
        self.kind = QComboBox()
        self.kind.addItems(("Tümü", "Analiz", "Backtest"))
        tools.addWidget(self.kind)
        tools.addWidget(QLabel("Ara"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Sembol, zaman dilimi, yön veya not")
        tools.addWidget(self.search, 1)
        self.refresh = QPushButton("Yenile")
        tools.addWidget(self.refresh)
        root.addLayout(tools)

        splitter = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(("Tarih", "Tür", "Sembol", "TF", "Yön", "Puan", "Karar", "R:R"))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        splitter.addWidget(self.table)

        details = QWidget()
        detail_layout = QVBoxLayout(details)
        detail_layout.addWidget(QLabel("Rapor ayrıntısı"))
        self.detail = QTextBrowser()
        detail_layout.addWidget(self.detail, 3)
        detail_layout.addWidget(QLabel("Kişisel not"))
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("Bu analize veya teste ait gözleminizi yazın…")
        self.note.setMaximumHeight(105)
        detail_layout.addWidget(self.note)
        note_tools = QHBoxLayout()
        note_tools.addWidget(QLabel("Etiketler"))
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("ör. NY, ters-trend, haber")
        note_tools.addWidget(self.tags, 1)
        self.save_note = QPushButton("Notu Kaydet")
        note_tools.addWidget(self.save_note)
        detail_layout.addLayout(note_tools)
        splitter.addWidget(details)
        splitter.setSizes((760, 440))
        root.addWidget(splitter, 1)
        self.status = QLabel("Raporlar yükleniyor…")
        self.status.setObjectName("muted")
        root.addWidget(self.status)

        self.kind.currentIndexChanged.connect(self._apply_filter)
        self.search.textChanged.connect(self._apply_filter)
        self.refresh.clicked.connect(self.refresh_requested)
        self.table.itemSelectionChanged.connect(self._show_selected)
        self.save_note.clicked.connect(self._save_note)

    def set_entries(self, entries: list[JournalEntry]) -> None:
        selected_id = self.current_entry_id()
        self._entries = entries
        self._apply_filter()
        if selected_id is not None:
            for row, entry in enumerate(self._visible):
                if entry.id == selected_id:
                    self.table.selectRow(row)
                    break
        self.status.setText(f"{len(entries)} kalıcı rapor · aynı kapanmış mum tekrar kaydedilmez")

    def current_entry_id(self) -> int | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.UserRole) if item is not None else None
        return int(value) if value is not None else None

    def _apply_filter(self) -> None:
        kind = {1: "ANALYSIS", 2: "BACKTEST"}.get(self.kind.currentIndex())
        query = self.search.text().strip().casefold()
        self._visible = [
            entry for entry in self._entries
            if (kind is None or entry.kind == kind)
            and (
                not query or query in " ".join(
                    (entry.symbol, entry.timeframe, entry.direction, entry.action, entry.summary, entry.note, entry.tags)
                ).casefold()
            )
        ]
        self.table.setRowCount(len(self._visible))
        for row, entry in enumerate(self._visible):
            created = entry.created_at.replace("T", " ")[:16]
            values = (
                created, "Analiz" if entry.kind == "ANALYSIS" else "Backtest", entry.symbol,
                entry.timeframe, entry.direction, str(entry.score), entry.action,
                f"{entry.rr:.2f}" if entry.rr is not None else "—",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, entry.id)
                if col in (4, 6):
                    color = GREEN if value in ("Yükseliş", "AL", "KÂRLI") else RED if value in ("Düşüş", "SAT", "ZARAR") else AMBER
                    item.setForeground(QColor(color))
                if col == 1:
                    item.setForeground(QColor(BLUE if entry.kind == "ANALYSIS" else AMBER))
                self.table.setItem(row, col, item)
        if self._visible:
            self.table.selectRow(0)
        else:
            self.detail.setText("Filtreye uygun rapor yok.")
            self.note.clear()
            self.tags.clear()

    @staticmethod
    def _metrics_html(entry: JournalEntry) -> str:
        metrics = entry.payload.get("metrics", {})
        rows = []
        for key, value in metrics.items():
            if isinstance(value, float):
                value = f"{value:,.4f}"
            rows.append(f"<tr><td>{escape(str(key))}</td><td><b>{escape(str(value))}</b></td></tr>")
        return "<table cellspacing='4'>" + "".join(rows) + "</table>"

    def _show_selected(self) -> None:
        entry_id = self.current_entry_id()
        entry = next((x for x in self._visible if x.id == entry_id), None)
        if entry is None:
            return
        note_html = f"<p><b>Not:</b> {escape(entry.note)}</p>" if entry.note else ""
        tags_html = f"<p><b>Etiketler:</b> {escape(entry.tags)}</p>" if entry.tags else ""
        self.detail.setHtml(
            f"<h3>{escape(entry.title)}</h3>"
            f"<p><b>Veri zamanı:</b> {escape(entry.asof.replace('T', ' ')[:19])} UTC</p>"
            f"<p><b>Özet:</b> {escape(entry.summary)}</p>{note_html}{tags_html}"
            f"<h4>Ölçümler</h4>{self._metrics_html(entry)}"
        )
        self.note.setPlainText(entry.note)
        self.tags.setText(entry.tags)

    def _save_note(self) -> None:
        entry_id = self.current_entry_id()
        if entry_id is None:
            self.status.setText("Not kaydetmek için bir rapor seçin.")
            return
        self.note_requested.emit(entry_id, self.note.toPlainText(), self.tags.text())

    def set_note_saved(self) -> None:
        self.status.setText("Not ve etiketler kaydedildi.")
