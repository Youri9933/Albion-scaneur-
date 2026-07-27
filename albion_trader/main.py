from __future__ import annotations

import logging
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from api import AlbionDataAPI
from config import AppConfig
from gui import MainWindow
from scanner import MarketScanner


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> int:
    configure_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Albion Trader Pro")
    app.setOrganizationName("Albion Trader Pro")
    app.setFont(QFont("Segoe UI", 10))

    config = AppConfig.load()
    api = AlbionDataAPI(server=config.api_server)
    scanner = MarketScanner(api)
    window = MainWindow(api, config, scanner)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
