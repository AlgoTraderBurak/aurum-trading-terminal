from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from aurum.ui.theme import GRID, MUTED, PANEL


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "—", parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:{PANEL};border:1px solid {GRID};border-radius:8px;}}"
            f"QLabel{{border:0;background:transparent;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.title = QLabel(title)
        self.title.setStyleSheet(f"color:{MUTED};font-size:9pt;")
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.value = QLabel(value)
        self.value.setStyleSheet("color:white;font-size:15pt;font-weight:600;")
        self.value.setMinimumWidth(0)
        self.value.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.title)
        layout.addWidget(self.value)

    def set_value(self, value: str, color: str | None = None) -> None:
        self.value.setText(value)
        self.value.setStyleSheet(
            f"color:{color or 'white'};font-size:15pt;font-weight:600;"
        )
