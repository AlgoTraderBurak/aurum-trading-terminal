from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from aurum.domain.models import AnalysisSnapshot, Direction, MarketDataBundle, Timeframe
from aurum.ui.chart import MarketChart
from aurum.ui.theme import AMBER, GREEN, RED
from aurum.ui.widgets import MetricCard


class LiveTab(QWidget):
    refresh_requested = Signal()
    selection_changed = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        toolbar = QHBoxLayout()
        title = QLabel("Canlı Grafik")
        title.setObjectName("sectionTitle")
        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Sembol"))
        self.symbol = QComboBox()
        self.symbol.setEditable(True)
        self.symbol.addItems(["BTCUSD", "ETHUSD", "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD"])
        self.symbol.setCurrentText("XAUUSD")
        self.symbol.setMinimumWidth(125)
        toolbar.addWidget(self.symbol)
        toolbar.addWidget(QLabel("Zaman"))
        self.timeframe = QComboBox()
        self.timeframe.addItems([x.label for x in Timeframe])
        self.timeframe.setCurrentText("M15")
        toolbar.addWidget(self.timeframe)
        self.refresh = QPushButton("Şimdi Yenile")
        toolbar.addWidget(self.refresh)
        root.addLayout(toolbar)

        cards = QHBoxLayout()
        self.price_card = MetricCard("Fiyat")
        self.direction_card = MetricCard("Yön")
        self.regime_card = MetricCard("Piyasa Rejimi")
        self.signal_card = MetricCard("Son Sinyal")
        self.data_card = MetricCard("Veri Durumu")
        for card in (self.price_card, self.direction_card, self.regime_card, self.signal_card, self.data_card):
            cards.addWidget(card)
        root.addLayout(cards)

        layers = QVBoxLayout()
        layers.setSpacing(5)
        primary_layers = QHBoxLayout()
        secondary_layers = QHBoxLayout()
        primary_layers.setSpacing(12)
        secondary_layers.setSpacing(12)
        primary_layers.addWidget(QLabel("Katmanlar"))
        secondary_layers.addWidget(QLabel("Yardımcı"))
        self.layer_checks: dict[str, QCheckBox] = {}
        layer_specs = (
            ("trend", "AURUM", True),
            ("sessions", "Seans", True),
            ("structure", "Yapı / Likidite", True),
            ("zones", "FVG / IFVG / OB", True),
            ("levels", "Seviyeler", True),
            ("signals", "Sinyaller", True),
            ("panel", "Sağ panel", True),
            ("rsi", "RSI", False),
        )
        for index, (key, label, checked) in enumerate(layer_specs):
            box = QCheckBox(label)
            box.setChecked(checked)
            self.layer_checks[key] = box
            (primary_layers if index < 4 else secondary_layers).addWidget(box)
        primary_layers.addStretch()
        self.connection = QLabel("Bağlantı bekleniyor")
        self.connection.setObjectName("muted")
        self.connection.setMinimumWidth(0)
        self.connection.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        primary_layers.addWidget(self.connection)
        self.extra_indicator = QComboBox()
        self.extra_indicator.addItems(("Ek: Kapalı", "Ek: VWAP", "Ek: EMA 20/50", "Ek: EMA + VWAP"))
        self.extra_indicator.setToolTip("Ana görünümü kalabalıklaştırmadan yardımcı çizgileri açar")
        secondary_layers.addWidget(self.extra_indicator)
        self.reset_view = QPushButton("Görünümü sıfırla")
        self.reset_view.setToolTip("Yakınlaştırmayı ve tarih konumunu başlangıca döndürür")
        self.reset_view.setText("Sıfırla")
        secondary_layers.addWidget(self.reset_view)
        secondary_layers.addStretch()
        layers.addLayout(primary_layers)
        layers.addLayout(secondary_layers)
        root.addLayout(layers)

        self.chart = MarketChart()
        root.addWidget(self.chart, 1)
        help_text = QLabel("Yakınlaştırma: fare tekeri · Geçmiş: grafiği sürükle · Sıfırla: çift tık · Etiketler uzak görünümde otomatik sadeleşir · Sinyaller kapanmış mumdan")
        help_text.setObjectName("muted")
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        self.refresh.clicked.connect(self.refresh_requested)
        self.timeframe.currentTextChanged.connect(self._emit_selection)
        self.symbol.lineEdit().editingFinished.connect(self._emit_selection)
        for key, box in self.layer_checks.items():
            box.toggled.connect(lambda enabled, name=key: self.chart.set_layer(name, enabled))
        self.extra_indicator.currentIndexChanged.connect(self._extra_indicator_changed)
        self.reset_view.clicked.connect(self.chart.reset_view)

    def _extra_indicator_changed(self, index: int) -> None:
        self.chart.set_layer("vwap", index in (1, 3))
        self.chart.set_layer("ema", index in (2, 3))

    def _emit_selection(self) -> None:
        self.selection_changed.emit(self.symbol.currentText().strip(), self.timeframe.currentText())

    def current_selection(self) -> tuple[str, Timeframe]:
        return self.symbol.currentText().strip(), Timeframe.parse(self.timeframe.currentText())

    def set_loading(self, loading: bool) -> None:
        self.refresh.setEnabled(not loading)
        self.refresh.setText("Veri alınıyor…" if loading else "Şimdi Yenile")

    def set_error(self, message: str) -> None:
        first = message.splitlines()[0]
        self.connection.setText(first)
        self.connection.setStyleSheet(f"color:{RED};")
        self.data_card.set_value("HATA", RED)

    def set_snapshot(self, bundle: MarketDataBundle, snapshot: AnalysisSnapshot) -> None:
        self.chart.set_data(bundle, snapshot)
        digits = max(2, min(8, bundle.metadata.digits))
        self.price_card.set_value(f"{snapshot.price:.{digits}f}")
        direction_color = GREEN if snapshot.direction is Direction.LONG else RED if snapshot.direction is Direction.SHORT else AMBER
        self.direction_card.set_value(f"{snapshot.direction.tr} · {snapshot.score}/100", direction_color)
        self.regime_card.set_value(snapshot.regime)
        latest = snapshot.latest_signal
        signal_text = f"{latest.action.tr} · {latest.score}" if latest else "Yeni sinyal yok"
        signal_color = GREEN if latest and latest.direction is Direction.LONG else RED if latest and latest.direction is Direction.SHORT else AMBER
        self.signal_card.set_value(signal_text, signal_color)
        quality_color = GREEN if bundle.quality.status_tr == "SAĞLIKLI" else AMBER
        self.data_card.set_value(bundle.quality.status_tr, quality_color)
        current_note = " · açık mum grafikte" if bundle.current_bar is not None else ""
        resolved_note = (
            f" → {bundle.metadata.resolved}"
            if bundle.metadata.resolved and bundle.metadata.resolved.upper() != bundle.symbol.upper()
            else ""
        )
        self.connection.setText(f"{bundle.source} · {bundle.symbol}{resolved_note} · {bundle.fetched_at:%H:%M:%S} UTC{current_note}")
        live_source = not bundle.source.startswith("Önbellek")
        self.connection.setStyleSheet(f"color:{GREEN if live_source else AMBER};")
