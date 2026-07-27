from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import logging
import time

import requests


LOGGER = logging.getLogger(__name__)


class AlbionApiError(RuntimeError):
    pass


@dataclass(slots=True)
class PricePoint:
    item_id: str
    city: str
    quality: int
    sell_price_min: float
    sell_price_min_date: str
    buy_price_max: float
    buy_price_max_date: str


class AlbionDataAPI:
    SERVER_BASE_URLS = {
        "europe": "https://europe.albion-online-data.com",
        "americas": "https://west.albion-online-data.com",
        "asia": "https://east.albion-online-data.com",
    }

    def __init__(self, server: str = "europe", timeout: float = 20.0) -> None:
        self.server = server if server in self.SERVER_BASE_URLS else "europe"
        self.base_url = self.SERVER_BASE_URLS[self.server].rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "AlbionTraderPro/1.0"})

    def _request_json(self, endpoint: str, params: dict[str, str]) -> Any:
        url = f"{self.base_url}{endpoint}"
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                LOGGER.warning("API request failed on attempt %d for %s: %s", attempt + 1, url, exc)
                if attempt < 2:
                    time.sleep(0.75 * (attempt + 1))

        raise AlbionApiError(f"Request failed for {url}: {last_error}") from last_error

    @staticmethod
    def _join(values: list[str] | tuple[str, ...]) -> str:
        return ",".join(value for value in values if value)

    def fetch_prices(self, item_ids: list[str], locations: list[str], qualities: list[int] | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {"locations": self._join(locations)}
        if qualities:
            params["qualities"] = self._join([str(quality) for quality in qualities])
        endpoint = f"/api/v2/stats/prices/{self._join(item_ids)}.json"
        payload = self._request_json(endpoint, params)
        return payload if isinstance(payload, list) else []

    def fetch_history(self, item_ids: list[str], locations: list[str], qualities: list[int] | None = None, time_scale: int = 1) -> list[dict[str, Any]]:
        params: dict[str, str] = {"locations": self._join(locations), "time-scale": str(time_scale)}
        if qualities:
            params["qualities"] = self._join([str(quality) for quality in qualities])
        endpoint = f"/api/v2/stats/history/{self._join(item_ids)}.json"
        payload = self._request_json(endpoint, params)
        return payload if isinstance(payload, list) else []

    @staticmethod
    def extract_location(record: dict[str, Any]) -> str:
        return str(record.get("city") or record.get("location") or record.get("market") or "")

    @staticmethod
    def extract_item_id(record: dict[str, Any]) -> str:
        return str(record.get("item_id") or record.get("ItemId") or record.get("unique_name") or "")

    @staticmethod
    def extract_quality(record: dict[str, Any]) -> int:
        try:
            return int(record.get("quality") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def extract_sell_price(record: dict[str, Any]) -> float:
        try:
            return float(record.get("sell_price_min") or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def extract_buy_price(record: dict[str, Any]) -> float:
        try:
            return float(record.get("buy_price_max") or 0)
        except (TypeError, ValueError):
            return 0.0

    def build_price_index(self, records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        index: dict[tuple[str, str], dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            item_id = self.extract_item_id(record)
            city = self.extract_location(record)
            if not item_id or not city:
                continue
            index[(item_id, city)] = record
        return index

    def build_volume_index(self, records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        index: dict[tuple[str, str], dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            item_id = self.extract_item_id(record)
            city = self.extract_location(record)
            if not item_id or not city:
                continue
            history_points = record.get("data") or []
            latest_point: dict[str, Any] | None = None
            if isinstance(history_points, list) and history_points:
                for point in reversed(history_points):
                    if isinstance(point, dict):
                        latest_point = point
                        break
            index[(item_id, city)] = {
                "latest_volume": self.extract_history_volume(latest_point or {}),
                "latest_price": self.extract_history_price(latest_point or {}),
                "latest_timestamp": self.extract_history_timestamp(latest_point or {}),
            }
        return index

    @staticmethod
    def extract_history_volume(point: dict[str, Any]) -> int:
        try:
            return int(point.get("item_count") or point.get("count") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def extract_history_price(point: dict[str, Any]) -> float:
        try:
            return float(point.get("avg_price") or point.get("price") or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def extract_history_timestamp(point: dict[str, Any]) -> str:
        return str(point.get("timestamp") or "")
