from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aurum.domain.models import Direction, Timeframe
from aurum.service import DashboardCell
from aurum.ui.theme import AMBER, BLUE, GREEN, MUTED, PANEL_2, RED, TEXT
from aurum.ui.widgets import MetricCard


@dataclass(frozen=True)
class RadarRow:
    symbol: str
    score: int
    direction: Direction
    alignment: str
    signal: str
    regime: str
    session: str
    volatility: str
    freshness: str
    best_timeframe: Timeframe
    errors: int


class DashboardTab(QWidget):
    refresh_requested = Signal(list)
    open_requested = Signal(str, str)

    WEIGHTS = {
        Timeframe.M1: 0.35,
        Timeframe.M5: 0.55,
        Timeframe.M15: 0.9,
        Timeframe.H1: 1.4,
        Timeframe.H4: 2.0,
        Timeframe.D1: 2.4,
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        title = QLabel("Piyasa Radarı")
        title.setObjectName("sectionTitle")
        bar.addWidget(title)
        bar.addStretch()
        bar.addWidget(QLabel("İzleme listesi"))
        self.symbols = QLineEdit("BTCUSD, ETHUSD, XAUUSD, XAGUSD, EURUSD, GBPUSD")
        self.symbols.setMinimumWidth(390)
        bar.addWidget(self.symbols)
        self.refresh = QPushButton("Radarı Güncelle")
        bar.addWidget(self.refresh)
        root.addLayout(bar)

        cards = QHBoxLayout()
        self.market_count = MetricCard("İzlenen Piyasa")
        self.aligned_count = MetricCard("MTF Hizalı")
        self.opportunity_count = MetricCard("Güçlü Görünüm")
        self.error_count = MetricCard("Veri Sorunu")
        for card in (self.market_count, self.aligned_count, self.opportunity_count, self.error_count):
            cards.addWidget(card)
        root.addLayout(cards)

        note = QLabel(
            "Radar puanı yön gücü, üst zaman dilimi ağırlığı ve zaman dilimi uyumundan oluşur. "
            "Bir satıra çift tıklamak seçilen piyasayı Canlı Grafik'te açar."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        root.addWidget(note)

        splitter = QSplitter(Qt.Vertical)
        radar_box = QWidget()
        radar_layout = QVBoxLayout(radar_box)
        radar_layout.setContentsMargins(0, 0, 0, 0)
        radar_layout.addWidget(QLabel("Öncelikli fırsatlar"))
        self.radar = QTableWidget(0, 9)
        self.radar.setHorizontalHeaderLabels(
            ["Sembol", "Radar", "MTF Yön", "Hizalanma", "Güncel Sinyal", "Rejim", "Seans / Volatilite", "Veri", "Aç"]
        )
        self.radar.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.radar.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.radar.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.radar.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.radar.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.radar.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.radar.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.radar.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.radar.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.radar.verticalHeader().setVisible(False)
        self.radar.setAlternatingRowColors(True)
        self.radar.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.radar.setEditTriggers(QAbstractItemView.NoEditTriggers)
        radar_layout.addWidget(self.radar)
        splitter.addWidget(radar_box)

        heat_box = QWidget()
        heat_layout = QVBoxLayout(heat_box)
        heat_layout.setContentsMargins(0, 0, 0, 0)
        heat_layout.addWidget(QLabel("Zaman dilimi ısı haritası"))
        self.heatmap = QTableWidget(0, 1 + len(Timeframe))
        self.heatmap.setHorizontalHeaderLabels(["Sembol"] + [x.label for x in Timeframe])
        self.heatmap.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for index in range(1, 1 + len(Timeframe)):
            self.heatmap.horizontalHeader().setSectionResizeMode(index, QHeaderView.Stretch)
        self.heatmap.verticalHeader().setVisible(False)
        self.heatmap.setEditTriggers(QAbstractItemView.NoEditTriggers)
        heat_layout.addWidget(self.heatmap)
        splitter.addWidget(heat_box)
        splitter.setSizes([380, 270])
        root.addWidget(splitter, 1)

        self.status = QLabel("Radar kullanıcı isteğiyle güncellenir; canlı grafik yenilemesini engellemez.")
        self.status.setObjectName("muted")
        root.addWidget(self.status)
        self.refresh.clicked.connect(self._request)
        self.radar.itemDoubleClicked.connect(self._open_row)

    def _request(self) -> None:
        symbols = [x.strip().upper() for x in self.symbols.text().split(",") if x.strip()]
        self.refresh_requested.emit(list(dict.fromkeys(symbols)))

    def _open_row(self, item: QTableWidgetItem) -> None:
        anchor = self.radar.item(item.row(), 0)
        if anchor is not None:
            self.open_requested.emit(str(anchor.data(Qt.UserRole)), str(anchor.data(Qt.UserRole + 1)))

    def set_loading(self, loading: bool) -> None:
        self.refresh.setEnabled(not loading)
        self.refresh.setText("Piyasalar okunuyor…" if loading else "Radarı Güncelle")

    @classmethod
    def build_radar_rows(cls, cells: list[DashboardCell]) -> list[RadarRow]:
        grouped: dict[str, list[DashboardCell]] = {}
        for cell in cells:
            grouped.setdefault(cell.symbol, []).append(cell)
        rows: list[RadarRow] = []
        for symbol, group in grouped.items():
            valid = [x for x in group if not x.error]
            errors = len(group) - len(valid)
            if not valid:
                rows.append(RadarRow(symbol, 0, Direction.NEUTRAL, "Veri yok", "—", "Veri yok", "—", "—", "—", Timeframe.M15, errors))
                continue
            total_weight = sum(cls.WEIGHTS[x.timeframe] for x in valid)
            signed = sum(x.direction.value * x.score * cls.WEIGHTS[x.timeframe] for x in valid)
            normalized = signed / total_weight if total_weight else 0.0
            direction = Direction.LONG if normalized > 6 else Direction.SHORT if normalized < -6 else Direction.NEUTRAL
            directional = [x for x in valid if x.direction is not Direction.NEUTRAL]
            aligned = sum(x.direction is direction for x in directional) if direction is not Direction.NEUTRAL else 0
            alignment_ratio = aligned / len(directional) if directional else 0.0
            if alignment_ratio >= 0.8 and len(directional) >= 3:
                alignment = "Tam hizalı"
            elif alignment_ratio >= 0.6:
                alignment = "Kısmi hizalı"
            else:
                alignment = "Karışık"
            signal_cells = [x for x in valid if x.signal not in ("—", "İŞLEM YOK")]
            best = max(signal_cells or valid, key=lambda x: x.score * cls.WEIGHTS[x.timeframe])
            signal = f"{best.signal} · {best.timeframe.label}" if signal_cells else "İŞLEM YOK"
            score = int(min(100, abs(normalized) * (0.62 + 0.38 * alignment_ratio) + (8 if signal_cells else 0)))
            regime_source = max(valid, key=lambda x: cls.WEIGHTS[x.timeframe])
            regime = regime_source.regime
            intraday = next((x for x in valid if x.timeframe is Timeframe.M15), best)
            volatility_value = intraday.volatility_percentile
            volatility = f"%{volatility_value:.0f}" if volatility_value is not None and np.isfinite(volatility_value) else "—"
            newest = max((x.asof for x in valid if x.asof is not None), default=None)
            freshness = newest.strftime("%d.%m %H:%M") if isinstance(newest, pd.Timestamp) else "—"
            rows.append(RadarRow(symbol, score, direction, alignment, signal, regime, intraday.session or "—", volatility, freshness, best.timeframe, errors))
        return sorted(rows, key=lambda x: (x.score, -x.errors), reverse=True)

    @staticmethod
    def _direction_color(direction: Direction) -> str:
        return GREEN if direction is Direction.LONG else RED if direction is Direction.SHORT else AMBER

    def set_cells(self, cells: list[DashboardCell]) -> None:
        rows = self.build_radar_rows(cells)
        self.radar.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.symbol, str(row.score), row.direction.tr, row.alignment, row.signal,
                row.regime, f"{row.session} · ATR {row.volatility}", row.freshness,
                f"Grafiğe git · {row.best_timeframe.label}",
            )
            color = self._direction_color(row.direction)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row.symbol)
                item.setData(Qt.UserRole + 1, row.best_timeframe.label)
                if col in (1, 2, 4):
                    item.setForeground(QColor(color))
                elif row.errors and col == 7:
                    item.setForeground(QColor(AMBER))
                if col == 1:
                    background = QColor(color); background.setAlpha(28)
                    item.setBackground(background)
                    item.setTextAlignment(Qt.AlignCenter)
                if col == 8:
                    item.setForeground(QColor(BLUE))
                self.radar.setItem(row_index, col, item)
        self.radar.resizeRowsToContents()

        symbols = [row.symbol for row in rows]
        positions = {symbol: index for index, symbol in enumerate(symbols)}
        self.heatmap.setRowCount(len(symbols))
        for symbol, row_index in positions.items():
            item = QTableWidgetItem(symbol)
            item.setForeground(QColor(TEXT))
            self.heatmap.setItem(row_index, 0, item)
        for cell in cells:
            if cell.symbol not in positions:
                continue
            row_index = positions[cell.symbol]
            col = list(Timeframe).index(cell.timeframe) + 1
            if cell.error:
                item = QTableWidgetItem("Veri yok")
                item.setForeground(QColor(MUTED))
                item.setToolTip(cell.error)
            else:
                arrow = "▲" if cell.direction is Direction.LONG else "▼" if cell.direction is Direction.SHORT else "•"
                item = QTableWidgetItem(f"{arrow} {cell.score}\n{cell.signal}")
                color = QColor(self._direction_color(cell.direction))
                item.setForeground(color)
                background = QColor(color); background.setAlpha(18)
                item.setBackground(background)
                item.setToolTip(
                    f"{cell.symbol} {cell.timeframe.label}\nYön: {cell.direction.tr}\nRejim: {cell.regime}"
                    f"\nFiyat: {cell.price:g}\nKaynak: {cell.source}"
                )
            item.setTextAlignment(Qt.AlignCenter)
            self.heatmap.setItem(row_index, col, item)
        self.heatmap.resizeRowsToContents()

        errors = sum(1 for x in cells if x.error)
        aligned = sum(row.alignment == "Tam hizalı" for row in rows)
        opportunities = sum(row.score >= 60 for row in rows)
        self.market_count.set_value(str(len(rows)), BLUE)
        self.aligned_count.set_value(str(aligned), GREEN if aligned else AMBER)
        self.opportunity_count.set_value(str(opportunities), GREEN if opportunities else AMBER)
        self.error_count.set_value(str(errors), RED if errors else GREEN)
        self.status.setStyleSheet("")
        self.status.setText(f"{len(cells)} zaman dilimi hücresi · {len(rows)} piyasa · {errors} veri sorunu")

    def set_error(self, message: str) -> None:
        self.status.setText(message.splitlines()[0])
        self.status.setStyleSheet(f"color:{RED};")
