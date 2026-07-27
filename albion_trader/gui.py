from __future__ import annotations

from pathlib import Path
from typing import Any
import logging

import requests
import pandas as pd
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from api import AlbionDataAPI
from config import (
    API_SERVER_OPTIONS,
    AppConfig,
    BUY_CITY_OPTIONS,
    CATEGORY_OPTIONS,
    CITY_OPTIONS,
    EXPORT_DIR,
    LANGUAGE_OPTIONS,
    TIER_OPTIONS,
)
from scanner import MarketScanner, ScanPayload
from utils import format_currency, format_percent


LOGGER = logging.getLogger(__name__)
ITEM_ICON_BASE_URL = "https://render.albiononline.com/v1/item/{item_id}.png"


TEXTS = {
    "fr": {
        "window_title": "Albion Trader Pro",
        "hero": "Scanner d'arbitrage pour Albion Online",
        "subtitle": "Serveur Europe, prix les plus recents, filtres automatiques et exports.",
        "market_settings": "Parametres marche",
        "language": "Langue",
        "server": "Serveur API",
        "item_name": "Nom item",
        "item_code": "Code item",
        "buy_city": "Ville achat",
        "sell_city": "Ville vente",
        "buy_tax": "Taxe achat %",
        "sell_tax": "Taxe vente %",
        "min_profit": "Profit minimum",
        "min_volume": "Volume minimum",
        "refresh_seconds": "Actualisation (s)",
        "auto_refresh": "Actualisation auto",
        "filters": "Filtres",
        "categories": "Categories",
        "tiers": "Tiers",
        "actions": "Actions",
        "scan": "Lancer le scan",
        "stop": "Arreter",
        "export_csv": "Export CSV",
        "export_xlsx": "Export Excel XLSX",
        "tab_silver": "Top Profit Silver",
        "tab_percent": "Top Profit %",
        "tab_volume": "Top Profit Volume",
        "ready": "Pret.",
        "scan_running": "Scan en cours...",
        "scan_already": "Un scan est deja en cours.",
        "need_category": "Veuillez selectionner au moins une categorie.",
        "need_tier": "Veuillez selectionner au moins un tier.",
        "no_results": "Aucune opportunite ne correspond aux filtres.",
        "scan_done": "Pret: {count} opportunites affichees.",
        "csv_no_data": "Aucune donnee a exporter.",
        "csv_title": "Exporter CSV",
        "xlsx_title": "Exporter Excel",
        "csv_failed": "Echec de l'export CSV: {error}",
        "xlsx_failed": "Echec de l'export Excel: {error}",
        "language_fr": "Francais",
        "language_en": "English",
        "server_europe": "Europe",
        "server_americas": "Americas",
        "server_asia": "Asia",
    },
    "en": {
        "window_title": "Albion Trader Pro",
        "hero": "Arbitrage scanner for Albion Online",
        "subtitle": "Europe server, freshest prices, automatic filters, and export-ready results.",
        "market_settings": "Market settings",
        "language": "Language",
        "server": "API server",
        "item_name": "Item name",
        "item_code": "Item code",
        "buy_city": "Buy city",
        "sell_city": "Sell city",
        "buy_tax": "Buy tax %",
        "sell_tax": "Sell tax %",
        "min_profit": "Minimum profit",
        "min_volume": "Minimum volume",
        "refresh_seconds": "Refresh (s)",
        "auto_refresh": "Auto refresh",
        "filters": "Filters",
        "categories": "Categories",
        "tiers": "Tiers",
        "actions": "Actions",
        "scan": "Start scan",
        "stop": "Stop",
        "export_csv": "Export CSV",
        "export_xlsx": "Export Excel XLSX",
        "tab_silver": "Top Profit Silver",
        "tab_percent": "Top Profit %",
        "tab_volume": "Top Profit Volume",
        "ready": "Ready.",
        "scan_running": "Scanning...",
        "scan_already": "A scan is already running.",
        "need_category": "Please select at least one category.",
        "need_tier": "Please select at least one tier.",
        "no_results": "No opportunity matched the current filters.",
        "scan_done": "Ready: {count} opportunities displayed.",
        "csv_no_data": "No data to export.",
        "csv_title": "Export CSV",
        "xlsx_title": "Export Excel",
        "csv_failed": "CSV export failed: {error}",
        "xlsx_failed": "Excel export failed: {error}",
        "language_fr": "French",
        "language_en": "English",
        "server_europe": "Europe",
        "server_americas": "Americas",
        "server_asia": "Asia",
    },
}


class MainWindow(QMainWindow):
    def __init__(self, api: AlbionDataAPI, config: AppConfig, scanner: MarketScanner) -> None:
        super().__init__()
        self.api = api
        self.config = config
        self.scanner = scanner
        self.current_payload: ScanPayload | None = None
        self.dataframes: dict[str, pd.DataFrame] = {
            "raw": pd.DataFrame(),
            "silver": pd.DataFrame(),
            "percent": pd.DataFrame(),
            "volume": pd.DataFrame(),
        }
        self.icon_cache: dict[str, QIcon] = {}

        self.setWindowTitle("Albion Trader Pro")
        self.resize(self.config.window_width, self.config.window_height)

        self._build_ui()
        self._apply_theme()
        self._load_config_into_ui()
        self._connect_signals()
        self._sync_timer()
        self._set_scanner_state(False)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(14)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter)

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_panel.setMaximumWidth(380)

        self.title_box = QGroupBox("Albion Trader Pro", left_panel)
        title_box = self.title_box
        title_layout = QVBoxLayout(title_box)
        self.title_label = QLabel("Arbitrage scanner for Albion Online market data")
        title_label = self.title_label
        title_label.setWordWrap(True)
        title_label.setObjectName("heroLabel")
        self.subtitle_label = QLabel("Europe server, current prices, automated filtering, and export-ready results.")
        subtitle = self.subtitle_label
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtleLabel")
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle)
        left_layout.addWidget(title_box)

        self.market_box = QGroupBox("Market settings", left_panel)
        market_box = self.market_box
        market_layout = QVBoxLayout(market_box)
        market_layout.setSpacing(10)

        self.language_combo = QComboBox(market_box)
        self.language_combo.addItem("Francais", "fr")
        self.language_combo.addItem("English", "en")
        self.server_combo = QComboBox(market_box)
        self.server_combo.addItem("Europe", "europe")
        self.server_combo.addItem("Americas", "americas")
        self.server_combo.addItem("Asia", "asia")

        self.buy_city_combo = QComboBox(market_box)
        self.buy_city_combo.addItems(BUY_CITY_OPTIONS)
        self.sell_city_combo = QComboBox(market_box)
        self.sell_city_combo.addItems(CITY_OPTIONS)

        market_layout.addWidget(self._row_widget("Language", self.language_combo))
        market_layout.addWidget(self._row_widget("API server", self.server_combo))

        market_layout.addWidget(self._row_widget("Buy city", self.buy_city_combo))
        market_layout.addWidget(self._row_widget("Sell city", self.sell_city_combo))

        self.purchase_tax_spin = QDoubleSpinBox(market_box)
        self.purchase_tax_spin.setRange(0.0, 100.0)
        self.purchase_tax_spin.setDecimals(2)
        self.purchase_tax_spin.setSingleStep(0.25)
        self.sale_tax_spin = QDoubleSpinBox(market_box)
        self.sale_tax_spin.setRange(0.0, 100.0)
        self.sale_tax_spin.setDecimals(2)
        self.sale_tax_spin.setSingleStep(0.25)
        self.minimum_profit_spin = QDoubleSpinBox(market_box)
        self.minimum_profit_spin.setRange(0.0, 1_000_000_000.0)
        self.minimum_profit_spin.setDecimals(2)
        self.minimum_profit_spin.setSingleStep(100.0)
        self.minimum_volume_spin = QSpinBox(market_box)
        self.minimum_volume_spin.setRange(0, 1_000_000)
        self.refresh_seconds_spin = QSpinBox(market_box)
        self.refresh_seconds_spin.setRange(5, 3600)
        self.auto_refresh_checkbox = QCheckBox("Auto refresh", market_box)

        market_layout.addWidget(self._row_widget("Buy tax %", self.purchase_tax_spin))
        market_layout.addWidget(self._row_widget("Sell tax %", self.sale_tax_spin))
        market_layout.addWidget(self._row_widget("Min profit", self.minimum_profit_spin))
        market_layout.addWidget(self._row_widget("Min volume", self.minimum_volume_spin))
        market_layout.addWidget(self._row_widget("Refresh seconds", self.refresh_seconds_spin))
        market_layout.addWidget(self.auto_refresh_checkbox)
        left_layout.addWidget(market_box)

        self.filter_box = QGroupBox("Filters", left_panel)
        filter_box = self.filter_box
        filter_layout = QVBoxLayout(filter_box)
        filter_layout.setSpacing(10)

        category_label = QLabel("Categories")
        category_label.setObjectName("sectionLabel")
        filter_layout.addWidget(category_label)
        self.category_checkboxes: dict[str, QCheckBox] = {}
        for key, label in CATEGORY_OPTIONS:
            checkbox = QCheckBox(label, filter_box)
            self.category_checkboxes[key] = checkbox
            filter_layout.addWidget(checkbox)

        tier_label = QLabel("Tiers")
        tier_label.setObjectName("sectionLabel")
        filter_layout.addWidget(tier_label)
        self.tier_checkboxes: dict[str, QCheckBox] = {}
        for tier in TIER_OPTIONS:
            checkbox = QCheckBox(tier, filter_box)
            self.tier_checkboxes[tier] = checkbox
            filter_layout.addWidget(checkbox)

        left_layout.addWidget(filter_box)

        self.actions_box = QGroupBox("Actions", left_panel)
        actions_box = self.actions_box
        actions_layout = QVBoxLayout(actions_box)
        self.scan_button = QPushButton("Lancer le scan", actions_box)
        self.stop_button = QPushButton("Arreter", actions_box)
        self.export_csv_button = QPushButton("Export CSV", actions_box)
        self.export_xlsx_button = QPushButton("Export Excel XLSX", actions_box)
        actions_layout.addWidget(self.scan_button)
        actions_layout.addWidget(self.stop_button)
        actions_layout.addWidget(self.export_csv_button)
        actions_layout.addWidget(self.export_xlsx_button)
        left_layout.addWidget(actions_box)
        left_layout.addStretch(1)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(left_panel)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.status_label = QLabel("Ready.", right_panel)
        self.status_label.setObjectName("statusLabel")
        self.progress_bar = QProgressBar(right_panel)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.progress_bar)

        self.tabs = QTabWidget(right_panel)
        self.tabs.addTab(self._create_table_tab("Top Profit Silver"), "Top Profit Silver")
        self.tabs.addTab(self._create_table_tab("Top Profit %"), "Top Profit %")
        self.tabs.addTab(self._create_table_tab("Top Profit Volume"), "Top Profit Volume")
        right_layout.addWidget(self.tabs, 1)

        splitter.addWidget(scroll_area)
        splitter.addWidget(right_panel)
        splitter.setSizes([360, 1120])

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_refresh_timer)

    def _text(self, key: str) -> str:
        language_code = self.config.language if self.config.language in TEXTS else "fr"
        return TEXTS[language_code][key]

    def _item_icon(self, item_id: str) -> QIcon:
        cached_icon = self.icon_cache.get(item_id)
        if cached_icon is not None:
            return cached_icon

        icon = QIcon()
        try:
            response = requests.get(ITEM_ICON_BASE_URL.format(item_id=item_id), timeout=10)
            response.raise_for_status()
            pixmap = QPixmap()
            if pixmap.loadFromData(response.content) and not pixmap.isNull():
                icon = QIcon(pixmap)
        except Exception:
            LOGGER.warning("Could not load item icon for %s", item_id)

        self.icon_cache[item_id] = icon
        return icon

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(self._text("window_title"))
        self.title_box.setTitle("Albion Trader Pro")
        self.market_box.setTitle(self._text("market_settings"))
        self.filter_box.setTitle(self._text("filters"))
        self.actions_box.setTitle(self._text("actions"))
        self.title_label.setText(self._text("hero"))
        self.subtitle_label.setText(self._text("subtitle"))

        self.language_combo.setItemText(0, self._text("language_fr"))
        self.language_combo.setItemText(1, self._text("language_en"))
        self.server_combo.setItemText(0, self._text("server_europe"))
        self.server_combo.setItemText(1, self._text("server_americas"))
        self.server_combo.setItemText(2, self._text("server_asia"))

        self.scan_button.setText(self._text("scan"))
        self.stop_button.setText(self._text("stop"))
        self.export_csv_button.setText(self._text("export_csv"))
        self.export_xlsx_button.setText(self._text("export_xlsx"))

        self.tabs.setTabText(0, self._text("tab_silver"))
        self.tabs.setTabText(1, self._text("tab_percent"))
        self.tabs.setTabText(2, self._text("tab_volume"))

        headers = [
            self._text("item_name"),
            self._text("item_code"),
            self._text("buy_city"),
            "Buy price",
            self._text("sell_city"),
            "Sell price",
            "Profit silver",
            "Profit %",
            "Volume",
            "Profit total",
        ]
        for table in [self._silver_table, self._percent_table, self._volume_table]:
            table.setHorizontalHeaderLabels(headers)

        self.status_label.setText(self._text("ready"))

    def _create_table_tab(self, title: str) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel(title, container)
        header.setObjectName("tabHeader")
        layout.addWidget(header)

        table = QTableWidget(container)
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
            [
                self._text("item_name"),
                self._text("item_code"),
                self._text("buy_city"),
                "Buy price",
                self._text("sell_city"),
                "Sell price",
                "Profit silver",
                "Profit %",
                "Volume",
                "Profit total",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setIconSize(QSize(24, 24))
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(2, 10):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table)

        setattr(self, f"table_{len(self.tabs.findChildren(QTableWidget)) if hasattr(self, 'tabs') else 0}", table)
        return container

    @property
    def _silver_table(self) -> QTableWidget:
        return self.tabs.widget(0).findChild(QTableWidget)

    @property
    def _percent_table(self) -> QTableWidget:
        return self.tabs.widget(1).findChild(QTableWidget)

    @property
    def _volume_table(self) -> QTableWidget:
        return self.tabs.widget(2).findChild(QTableWidget)

    def _row_widget(self, label_text: str, control: QWidget) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel(label_text, row)
        label.setMinimumWidth(130)
        layout.addWidget(label)
        layout.addWidget(control, 1)
        return row

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setFont(QFont("Segoe UI", 10))
            app.setStyleSheet(
                """
                QWidget {
                    background-color: #0f141c;
                    color: #e6edf3;
                    font-size: 10.5pt;
                }
                QMainWindow {
                    background-color: #0f141c;
                }
                QGroupBox {
                    border: 1px solid #233041;
                    border-radius: 10px;
                    margin-top: 16px;
                    padding: 10px;
                    background-color: #121923;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 6px;
                    color: #9ddcff;
                }
                QLabel#heroLabel {
                    font-size: 17pt;
                    font-weight: 700;
                    color: #f5f7fb;
                }
                QLabel#subtleLabel {
                    color: #8ea2b8;
                }
                QLabel#sectionLabel {
                    font-size: 11pt;
                    font-weight: 600;
                    color: #9ddcff;
                    padding-top: 6px;
                }
                QLabel#tabHeader {
                    font-size: 12pt;
                    font-weight: 600;
                    color: #f5f7fb;
                    padding: 2px 0 6px 0;
                }
                QLabel#statusLabel {
                    color: #cbd5e1;
                    font-weight: 500;
                }
                QPushButton {
                    background-color: #172230;
                    border: 1px solid #294157;
                    border-radius: 8px;
                    padding: 9px 12px;
                    color: #f7fbff;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #223349;
                    border-color: #376181;
                }
                QPushButton:pressed {
                    background-color: #101823;
                }
                QPushButton:disabled {
                    background-color: #121820;
                    color: #7b8896;
                    border-color: #1f2935;
                }
                QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
                    background-color: #111824;
                    border: 1px solid #2a3a4e;
                    border-radius: 8px;
                    padding: 7px 9px;
                    selection-background-color: #3b82f6;
                }
                QComboBox::drop-down {
                    border: 0;
                    width: 24px;
                }
                QComboBox QAbstractItemView {
                    background-color: #111824;
                    selection-background-color: #24507a;
                    border: 1px solid #2a3a4e;
                }
                QCheckBox {
                    spacing: 8px;
                }
                QProgressBar {
                    background-color: #111824;
                    border: 1px solid #2a3a4e;
                    border-radius: 8px;
                    height: 12px;
                }
                QProgressBar::chunk {
                    background-color: #2dd4bf;
                    border-radius: 8px;
                }
                QTabWidget::pane {
                    border: 1px solid #233041;
                    border-radius: 10px;
                    background-color: #121923;
                    top: -1px;
                }
                QTabBar::tab {
                    background-color: #172230;
                    color: #a9bdd1;
                    border: 1px solid #233041;
                    border-bottom: 0;
                    padding: 10px 14px;
                    margin-right: 4px;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                }
                QTabBar::tab:selected {
                    background-color: #121923;
                    color: #ffffff;
                    border-color: #3b82f6;
                }
                QTableWidget {
                    background-color: #121923;
                    gridline-color: #233041;
                    border: 1px solid #233041;
                    border-radius: 10px;
                    alternate-background-color: #0f1620;
                }
                QHeaderView::section {
                    background-color: #172230;
                    color: #e6edf3;
                    border: none;
                    border-bottom: 1px solid #233041;
                    padding: 8px;
                    font-weight: 600;
                }
                QScrollArea {
                    border: none;
                    background: transparent;
                }
                QToolTip {
                    background-color: #172230;
                    color: #e6edf3;
                    border: 1px solid #294157;
                }
                """
            )

    def _connect_signals(self) -> None:
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.server_combo.currentIndexChanged.connect(self._on_server_changed)
        self.scan_button.clicked.connect(self.start_scan)
        self.stop_button.clicked.connect(self.stop_scan)
        self.export_csv_button.clicked.connect(self.export_csv)
        self.export_xlsx_button.clicked.connect(self.export_xlsx)

        for widget in [
            self.buy_city_combo,
            self.sell_city_combo,
            self.purchase_tax_spin,
            self.sale_tax_spin,
            self.minimum_profit_spin,
            self.minimum_volume_spin,
            self.refresh_seconds_spin,
            self.auto_refresh_checkbox,
        ]:
            if isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self._on_settings_changed)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._on_settings_changed)
            else:
                widget.valueChanged.connect(self._on_settings_changed)

        for checkbox in self.category_checkboxes.values():
            checkbox.stateChanged.connect(self._on_settings_changed)
        for checkbox in self.tier_checkboxes.values():
            checkbox.stateChanged.connect(self._on_settings_changed)

        self.tabs.currentChanged.connect(self._persist_selected_tab)
        self.scanner.progress.connect(self._set_status)
        self.scanner.error.connect(self._on_scan_error)
        self.scanner.finished.connect(self._on_scan_finished)
        self.scanner.state_changed.connect(self._set_scanner_state)

    def _load_config_into_ui(self) -> None:
        language_index = self.language_combo.findData(self.config.language)
        if language_index >= 0:
            self.language_combo.setCurrentIndex(language_index)
        server_index = self.server_combo.findData(self.config.api_server)
        if server_index >= 0:
            self.server_combo.setCurrentIndex(server_index)
        self.buy_city_combo.setCurrentText(self.config.buy_city)
        self.sell_city_combo.setCurrentText(self.config.sell_city)
        self.purchase_tax_spin.setValue(self.config.purchase_tax)
        self.sale_tax_spin.setValue(self.config.sale_tax)
        self.minimum_profit_spin.setValue(self.config.minimum_profit)
        self.minimum_volume_spin.setValue(self.config.minimum_volume)
        self.refresh_seconds_spin.setValue(self.config.refresh_seconds)
        self.auto_refresh_checkbox.setChecked(self.config.auto_refresh)

        for key, checkbox in self.category_checkboxes.items():
            checkbox.setChecked(key in self.config.selected_categories)
        for tier, checkbox in self.tier_checkboxes.items():
            checkbox.setChecked(tier in self.config.selected_tiers)

        self.tabs.setCurrentIndex(min(max(self.config.selected_tab_index, 0), self.tabs.count() - 1))
        self._retranslate_ui()
        self._persist_config()

    def _on_language_changed(self, *_args: object) -> None:
        selected = self.language_combo.currentData()
        if isinstance(selected, str) and selected in {code for code, _ in LANGUAGE_OPTIONS}:
            self.config.language = selected
            self._retranslate_ui()
            self._persist_config()

    def _on_server_changed(self, *_args: object) -> None:
        selected = self.server_combo.currentData()
        if isinstance(selected, str) and selected in {code for code, _ in API_SERVER_OPTIONS}:
            self.config.api_server = selected
            self._persist_config()

    def _collect_config_from_ui(self) -> None:
        self.config.buy_city = self.buy_city_combo.currentText()
        self.config.sell_city = self.sell_city_combo.currentText()
        self.config.purchase_tax = float(self.purchase_tax_spin.value())
        self.config.sale_tax = float(self.sale_tax_spin.value())
        self.config.minimum_profit = float(self.minimum_profit_spin.value())
        self.config.minimum_volume = int(self.minimum_volume_spin.value())
        self.config.refresh_seconds = int(self.refresh_seconds_spin.value())
        self.config.auto_refresh = bool(self.auto_refresh_checkbox.isChecked())
        self.config.selected_categories = [key for key, checkbox in self.category_checkboxes.items() if checkbox.isChecked()]
        self.config.selected_tiers = [tier for tier, checkbox in self.tier_checkboxes.items() if checkbox.isChecked()]
        self.config.selected_tab_index = int(self.tabs.currentIndex())
        self.config.window_width = int(self.width())
        self.config.window_height = int(self.height())

    def _persist_config(self) -> None:
        self._collect_config_from_ui()
        try:
            self.config.save()
        except OSError as exc:
            LOGGER.warning("Could not save config: %s", exc)

    def _persist_selected_tab(self) -> None:
        self._collect_config_from_ui()
        self._persist_timer()
        self._persist_config()

    def _on_settings_changed(self) -> None:
        self._persist_config()
        self._sync_timer()

    def _persist_timer(self) -> None:
        if self.auto_refresh_checkbox.isChecked():
            self.timer.start(self.refresh_seconds_spin.value() * 1000)
        else:
            self.timer.stop()

    def _sync_timer(self) -> None:
        self._persist_timer()

    def _on_refresh_timer(self) -> None:
        if not self.scanner.is_running:
            self.start_scan()

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        LOGGER.info(message)

    def _on_scan_error(self, message: str) -> None:
        self.status_label.setText(message)
        LOGGER.error(message)
        QMessageBox.critical(self, "Albion Trader Pro", message)

    def _set_scanner_state(self, running: bool) -> None:
        self.scan_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.progress_bar.setRange(0, 0 if running else 100)
        if not running:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        self.auto_refresh_checkbox.setEnabled(not running)
        self._persist_config()
        if not running:
            self._sync_timer()

    def start_scan(self) -> None:
        self._collect_config_from_ui()
        if not self.config.selected_categories:
            QMessageBox.warning(self, "Albion Trader Pro", self._text("need_category"))
            return
        if not self.config.selected_tiers:
            QMessageBox.warning(self, "Albion Trader Pro", self._text("need_tier"))
            return
        if self.scanner.is_running:
            self.status_label.setText(self._text("scan_already"))
            return
        self._persist_config()
        started = self.scanner.start_scan(self.config)
        if started:
            self.status_label.setText(self._text("scan_running"))
        else:
            self.status_label.setText(self._text("scan_already"))

    def stop_scan(self) -> None:
        self.scanner.stop_scan()

    def _on_scan_finished(self, payload: object) -> None:
        if isinstance(payload, ScanPayload):
            self.current_payload = payload
            self.dataframes = {
                "raw": payload.raw,
                "silver": payload.top_profit_silver,
                "percent": payload.top_profit_percent,
                "volume": payload.top_profit_volume,
            }
            self._populate_tables()
            self.status_label.setText(self._text("scan_done").format(count=len(payload.raw)))
        else:
            self.current_payload = None
            self.dataframes = {"raw": pd.DataFrame(), "silver": pd.DataFrame(), "percent": pd.DataFrame(), "volume": pd.DataFrame()}
            self._clear_tables()
        self._sync_timer()

    def _clear_tables(self) -> None:
        for table in [self._silver_table, self._percent_table, self._volume_table]:
            table.setRowCount(0)

    def _populate_tables(self) -> None:
        self._populate_table(self._silver_table, self.dataframes["silver"])
        self._populate_table(self._percent_table, self.dataframes["percent"])
        self._populate_table(self._volume_table, self.dataframes["volume"])

    def _populate_table(self, table: QTableWidget, dataframe: pd.DataFrame) -> None:
        table.setSortingEnabled(False)
        table.clearContents()
        if dataframe is None or dataframe.empty:
            table.setRowCount(0)
            return

        table.setRowCount(len(dataframe))
        for row_index, (_, row) in enumerate(dataframe.iterrows()):
            values = [
                str(row.get("item_name", "")),
                str(row.get("item_id", "")),
                str(row.get("buy_city", "")),
                format_currency(row.get("buy_price")),
                str(row.get("sell_city", "")),
                format_currency(row.get("sell_price")),
                format_currency(row.get("profit_silver")),
                format_percent(row.get("profit_pct")),
                format_currency(row.get("volume")),
                format_currency(row.get("profit_total")),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setIcon(self._item_icon(str(row.get("item_id", ""))))
                if column_index in {3, 5, 6, 8, 9}:
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                elif column_index == 7:
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()
        table.setSortingEnabled(True)

    def export_csv(self) -> None:
        if self.dataframes["raw"].empty:
            QMessageBox.information(self, "Albion Trader Pro", self._text("csv_no_data"))
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._text("csv_title"),
            str(EXPORT_DIR / "albion_trader_pro_export.csv"),
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            self.dataframes["raw"].to_csv(path, index=False, encoding="utf-8-sig")
            self.status_label.setText(f"CSV exported to {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Albion Trader Pro", self._text("csv_failed").format(error=exc))

    def export_xlsx(self) -> None:
        if self.dataframes["raw"].empty:
            QMessageBox.information(self, "Albion Trader Pro", self._text("csv_no_data"))
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._text("xlsx_title"),
            str(EXPORT_DIR / "albion_trader_pro_export.xlsx"),
            "Excel Files (*.xlsx)",
        )
        if not path:
            return
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                self.dataframes["raw"].to_excel(writer, index=False, sheet_name="Raw")
                self.dataframes["silver"].to_excel(writer, index=False, sheet_name="Top_Silver")
                self.dataframes["percent"].to_excel(writer, index=False, sheet_name="Top_Percent")
                self.dataframes["volume"].to_excel(writer, index=False, sheet_name="Top_Volume")
            self.status_label.setText(f"Excel exported to {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Albion Trader Pro", self._text("xlsx_failed").format(error=exc))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._persist_config()
        self.timer.stop()
        if self.scanner.is_running:
            self.scanner.stop_scan()
        super().closeEvent(event)
