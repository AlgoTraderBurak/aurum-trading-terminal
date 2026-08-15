from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from aurum.analysis.engine import AnalysisEngine
from aurum.data.quality import validate_bars
from aurum.domain.models import MarketDataBundle, SymbolMetadata, Timeframe
from aurum.ui.chart import MarketChart


def test_session_spans_keep_contiguous_ranges_separate():
    index = pd.date_range("2026-08-12 00:00", periods=8, freq="15min", tz="UTC")
    labels = pd.Series(
        ["Asya", "Asya", "Kapalı/Geçiş", "Londra", "Londra", "Londra", "New York", "New York"],
        index=index,
    )

    assert MarketChart._session_spans(index, labels) == [
        (0, 1, "Asya"),
        (3, 5, "Londra"),
        (6, 7, "New York"),
    ]


def test_structure_event_labels_are_compact_and_turkish():
    assert MarketChart._event_label("CHOCH_BULL") == "CHoCH ↑"
    assert MarketChart._event_label("BOS_BEAR") == "BOS ↓"
    assert MarketChart._event_label("SWEEP_LOW") == "LQ süpürme ↑"


def test_status_panel_ignores_uncomputed_open_bar(bars):
    app = QApplication.instance() or QApplication([])
    closed = bars.iloc[:-1]
    current = bars.iloc[-1]
    bundle = MarketDataBundle(
        "TEST", "TEST", Timeframe.M15, bars, closed, current, "Test",
        SymbolMetadata("TEST", "TEST", digits=2, point=.01, tick_size=.01),
        validate_bars(closed, Timeframe.M15, continuous=True, now=closed.index[-1]),
        pd.Timestamp.now(tz="UTC"),
    )
    snapshot = AnalysisEngine().analyze(bundle)
    chart = MarketChart()
    chart.set_data(bundle, snapshot)
    view = snapshot.frame.copy()
    open_row = current.reindex(view.columns)
    view.loc[bars.index[-1]] = open_row
    assert pd.isna(view.iloc[-1]["structure_bias"])
    image = QImage(320, 500, QImage.Format_ARGB32)
    painter = QPainter(image)
    chart._draw_status_panel(painter, QRectF(0, 0, 320, 500), view)
    painter.end()
    assert not image.isNull()
