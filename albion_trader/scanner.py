from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import logging
import threading

import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

from api import AlbionApiError, AlbionDataAPI
from config import AppConfig
from utils import CatalogItem, batched, filter_catalog, format_item_name, load_catalog


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ScanPayload:
    raw: pd.DataFrame
    top_profit_silver: pd.DataFrame
    top_profit_percent: pd.DataFrame
    top_profit_volume: pd.DataFrame


class MarketScanner(QObject):
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal(object)
    state_changed = pyqtSignal(bool)

    def __init__(self, api: AlbionDataAPI) -> None:
        super().__init__()
        self.api = api
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start_scan(self, config: AppConfig) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_scan, args=(config,), daemon=True)
            self._thread.start()
            self.state_changed.emit(True)
            return True

    def stop_scan(self) -> None:
        self._stop_event.set()
        self.progress.emit("Stopping current scan...")

    def _emit_finished(self, payload: ScanPayload | None = None) -> None:
        if payload is None:
            payload = ScanPayload(
                raw=pd.DataFrame(),
                top_profit_silver=pd.DataFrame(),
                top_profit_percent=pd.DataFrame(),
                top_profit_volume=pd.DataFrame(),
            )
        self.finished.emit(payload)
        self.state_changed.emit(False)

    def _run_scan(self, config: AppConfig) -> None:
        try:
            self.progress.emit("Loading item catalog...")
            catalog = load_catalog()
            selected_items = filter_catalog(catalog, config.selected_categories, config.selected_tiers)
            if not selected_items:
                self.error.emit("No items matched the selected categories and tiers.")
                self._emit_finished()
                return

            self.progress.emit(f"Scanning {len(selected_items)} items across {config.buy_city} -> {config.sell_city}...")
            rows: list[dict[str, Any]] = []
            batch_size = 40
            locations = [config.buy_city, config.sell_city]
            selected_ids = [item.item_id for item in selected_items]
            total_batches = max(1, (len(selected_ids) + batch_size - 1) // batch_size)

            for batch_index, item_batch_ids in enumerate(batched(selected_ids, batch_size), start=1):
                if self._stop_event.is_set():
                    self.progress.emit("Scan stopped by user.")
                    break

                batch_items = [item for item in selected_items if item.item_id in set(item_batch_ids)]
                try:
                    price_records = self.api.fetch_prices(item_batch_ids, locations, qualities=[1])
                    history_records = self.api.fetch_history(item_batch_ids, locations, qualities=[1], time_scale=1)
                except AlbionApiError as exc:
                    LOGGER.warning("Skipping batch %s due to API error: %s", batch_index, exc)
                    self.progress.emit(f"Batch {batch_index}/{total_batches} failed, continuing...")
                    continue
                except Exception as exc:  # pragma: no cover - defensive
                    LOGGER.exception("Unexpected error while scanning batch")
                    self.progress.emit(f"Unexpected error on batch {batch_index}: {exc}")
                    continue

                price_index = self.api.build_price_index(price_records)
                volume_index = self.api.build_volume_index(history_records)

                for item in batch_items:
                    buy_record = price_index.get((item.item_id, config.buy_city))
                    sell_record = price_index.get((item.item_id, config.sell_city))
                    if not buy_record or not sell_record:
                        continue

                    buy_price = self.api.extract_sell_price(buy_record)
                    sell_price = self.api.extract_buy_price(sell_record)
                    if buy_price <= 0 or sell_price <= 0:
                        continue

                    buy_net = buy_price * (1.0 + (config.purchase_tax / 100.0))
                    sell_net = sell_price * (1.0 - (config.sale_tax / 100.0))
                    profit_unit = sell_net - buy_net
                    if profit_unit < config.minimum_profit:
                        continue

                    profit_pct = (profit_unit / buy_net * 100.0) if buy_net > 0 else 0.0
                    buy_volume = volume_index.get((item.item_id, config.buy_city), {}).get("latest_volume", 0)
                    sell_volume = volume_index.get((item.item_id, config.sell_city), {}).get("latest_volume", 0)
                    positive_volumes = [volume for volume in (buy_volume, sell_volume) if isinstance(volume, int) and volume > 0]
                    available_volume = min(positive_volumes) if positive_volumes else 0
                    if available_volume < config.minimum_volume:
                        continue

                    profit_total = profit_unit * available_volume
                    display_name = item.name if config.language == "en" else format_item_name(item.item_id, config.language)
                    rows.append(
                        {
                            "item_id": item.item_id,
                            "item_name": display_name,
                            "tier": item.tier,
                            "category": item.category,
                            "buy_city": config.buy_city,
                            "sell_city": config.sell_city,
                            "buy_price": round(buy_price, 2),
                            "sell_price": round(sell_price, 2),
                            "buy_price_net": round(buy_net, 2),
                            "sell_price_net": round(sell_net, 2),
                            "profit_silver": round(profit_unit, 2),
                            "profit_pct": round(profit_pct, 2),
                            "volume": int(available_volume),
                            "profit_total": round(profit_total, 2),
                            "buy_price_date": str(buy_record.get("sell_price_min_date") or ""),
                            "sell_price_date": str(sell_record.get("buy_price_max_date") or ""),
                        }
                    )

                self.progress.emit(f"Completed batch {batch_index}/{total_batches}: {len(rows)} opportunities found so far.")

            dataframe = pd.DataFrame(rows)
            if dataframe.empty:
                payload = ScanPayload(
                    raw=dataframe,
                    top_profit_silver=dataframe,
                    top_profit_percent=dataframe,
                    top_profit_volume=dataframe,
                )
                self.progress.emit("No arbitrage opportunities matched the current filters.")
                self._emit_finished(payload)
                return

            numeric_columns = ["buy_price", "sell_price", "buy_price_net", "sell_price_net", "profit_silver", "profit_pct", "volume", "profit_total"]
            for column in numeric_columns:
                dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0)

            dataframe = dataframe.sort_values(by=["profit_silver", "profit_total", "volume"], ascending=[False, False, False]).reset_index(drop=True)
            top_profit_silver = dataframe.sort_values(by=["profit_silver", "profit_total"], ascending=[False, False]).reset_index(drop=True)
            top_profit_percent = dataframe.sort_values(by=["profit_pct", "profit_silver"], ascending=[False, False]).reset_index(drop=True)
            top_profit_volume = dataframe.sort_values(by=["profit_total", "volume"], ascending=[False, False]).reset_index(drop=True)

            payload = ScanPayload(
                raw=dataframe,
                top_profit_silver=top_profit_silver,
                top_profit_percent=top_profit_percent,
                top_profit_volume=top_profit_volume,
            )
            self.progress.emit(f"Scan complete: {len(dataframe)} opportunities ready.")
            self._emit_finished(payload)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("Fatal scan error")
            self.error.emit(f"Scan failed: {exc}")
            self._emit_finished()
        finally:
            with self._lock:
                self._thread = None
                self._stop_event.clear()
