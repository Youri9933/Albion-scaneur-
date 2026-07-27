from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.json"
EXPORT_DIR = APP_DIR / "exports"

API_SERVER_OPTIONS = [
    ("europe", "Europe"),
    ("americas", "Americas"),
    ("asia", "Asia"),
]

LANGUAGE_OPTIONS = [
    ("fr", "Francais"),
    ("en", "English"),
]

CITY_OPTIONS = [
    "Martlock",
    "Bridgewatch",
    "Fort Sterling",
    "Lymhurst",
    "Thetford",
    "Caerleon",
    "Black Market",
]

BUY_CITY_OPTIONS = [city for city in CITY_OPTIONS if city != "Black Market"]

CATEGORY_OPTIONS = [
    ("resources", "Resources"),
    ("equipment", "Equipment"),
    ("weapons", "Weapons"),
    ("armors", "Armors"),
    ("bags", "Bags"),
    ("capes", "Capes"),
    ("mounts", "Mounts"),
]

TIER_OPTIONS = ["T4", "T5", "T6", "T7", "T8"]


@dataclass(slots=True)
class AppConfig:
    language: str = "fr"
    api_server: str = "europe"
    buy_city: str = "Martlock"
    sell_city: str = "Caerleon"
    purchase_tax: float = 0.0
    sale_tax: float = 4.0
    minimum_profit: float = 500.0
    minimum_volume: int = 10
    refresh_seconds: int = 30
    auto_refresh: bool = False
    selected_categories: list[str] = field(
        default_factory=lambda: ["resources", "equipment", "weapons", "armors", "bags", "capes", "mounts"]
    )
    selected_tiers: list[str] = field(default_factory=lambda: ["T4", "T5", "T6", "T7", "T8"])
    selected_tab_index: int = 0
    window_width: int = 1500
    window_height: int = 920

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppConfig":
        base = cls()
        if not isinstance(payload, dict):
            return base

        data = asdict(base)
        for key in data:
            if key in payload:
                data[key] = payload[key]

        data["language"] = str(data.get("language") or base.language).lower()
        if data["language"] not in {code for code, _ in LANGUAGE_OPTIONS}:
            data["language"] = base.language
        data["api_server"] = str(data.get("api_server") or base.api_server).lower()
        if data["api_server"] not in {code for code, _ in API_SERVER_OPTIONS}:
            data["api_server"] = base.api_server
        data["buy_city"] = str(data.get("buy_city") or base.buy_city)
        data["sell_city"] = str(data.get("sell_city") or base.sell_city)
        data["purchase_tax"] = float(data.get("purchase_tax", base.purchase_tax))
        data["sale_tax"] = float(data.get("sale_tax", base.sale_tax))
        data["minimum_profit"] = float(data.get("minimum_profit", base.minimum_profit))
        data["minimum_volume"] = int(data.get("minimum_volume", base.minimum_volume))
        data["refresh_seconds"] = max(5, int(data.get("refresh_seconds", base.refresh_seconds)))
        data["auto_refresh"] = bool(data.get("auto_refresh", base.auto_refresh))
        data["selected_categories"] = [
            str(value)
            for value in data.get("selected_categories", base.selected_categories)
            if str(value)
        ]
        data["selected_tiers"] = [
            str(value)
            for value in data.get("selected_tiers", base.selected_tiers)
            if str(value)
        ]
        data["selected_tab_index"] = int(data.get("selected_tab_index", base.selected_tab_index))
        data["window_width"] = int(data.get("window_width", base.window_width))
        data["window_height"] = int(data.get("window_height", base.window_height))
        return cls(**data)

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "AppConfig":
        if not path.exists():
            return cls()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
