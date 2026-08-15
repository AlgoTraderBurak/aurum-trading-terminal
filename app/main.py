from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from aurum.ui.main_window import MainWindow
from aurum.ui.theme import APP_STYLESHEET


ROOT = Path(__file__).resolve().parents[1]


def _configure_logging() -> None:
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(ROOT / "logs" / "aurum.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main() -> int:
    _configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("AURUM")
    app.setOrganizationName("AURUM")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    def handle_exception(exc_type, exc_value, exc_traceback):
        logging.getLogger("aurum").exception(
            "Beklenmeyen uygulama hatası", exc_info=(exc_type, exc_value, exc_traceback)
        )
        QMessageBox.critical(None, "AURUM Hatası", f"Beklenmeyen hata:\n{exc_value}")

    sys.excepthook = handle_exception
    window = MainWindow(ROOT)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
