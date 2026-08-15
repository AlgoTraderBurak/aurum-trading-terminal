BG = "#0b0f16"
PANEL = "#111827"
PANEL_2 = "#172033"
GRID = "#243047"
TEXT = "#e5e7eb"
MUTED = "#8b9bb4"
BLUE = "#4ea1ff"
GREEN = "#20c997"
RED = "#ff5c70"
AMBER = "#f3b33d"
PURPLE = "#a78bfa"


APP_STYLESHEET = f"""
QMainWindow, QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI'; font-size: 10pt; }}
QTabWidget::pane {{ border: 1px solid {GRID}; border-radius: 8px; background: {BG}; }}
QTabBar::tab {{ background: {PANEL}; color: {MUTED}; padding: 11px 22px; margin-right: 2px; }}
QTabBar::tab:selected {{ color: white; background: {PANEL_2}; border-bottom: 2px solid {BLUE}; }}
QPushButton {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {GRID}; border-radius: 6px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {BLUE}; }}
QPushButton:pressed {{ background: #1f2a40; }}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{ background: {PANEL}; border: 1px solid {GRID}; border-radius: 5px; padding: 6px; color: {TEXT}; }}
QComboBox QAbstractItemView {{ background: {PANEL}; selection-background-color: {PANEL_2}; }}
QTableWidget {{ background: {PANEL}; alternate-background-color: #0e1624; border: 1px solid {GRID}; gridline-color: {GRID}; selection-background-color: #203a5c; }}
QHeaderView::section {{ background: {PANEL_2}; color: {MUTED}; padding: 7px; border: 0; border-right: 1px solid {GRID}; }}
QTextBrowser {{ background: {PANEL}; border: 1px solid {GRID}; border-radius: 7px; padding: 8px; }}
QCheckBox {{ spacing: 6px; color: {MUTED}; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}
QLabel#sectionTitle {{ font-size: 15pt; font-weight: 600; color: white; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#statusGood {{ color: {GREEN}; font-weight: 600; }}
QLabel#statusWarn {{ color: {AMBER}; font-weight: 600; }}
"""
