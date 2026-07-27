from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json
import logging
import re

import requests

from config import CATEGORY_OPTIONS, TIER_OPTIONS


LOGGER = logging.getLogger(__name__)
REMOTE_ITEMS_URL = "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/formatted/items.json"
TIER_RE = re.compile(r"^T([4-8])_")

RESOURCE_SUFFIXES = {"ORE", "WOOD", "FIBER", "HIDE", "ROCK", "METALBAR", "PLANKS", "CLOTH", "LEATHER", "BLOCK"}
WEAPON_MARKERS = ("MAIN_", "2H_")
ARMOR_MARKERS = ("HEAD_", "ARMOR_", "SHOES_")
BAG_MARKERS = ("BAG",)
CAPE_MARKERS = ("CAPE",)
MOUNT_MARKERS = ("MOUNT_", "HORSE", "OX", "MAMMOTH", "WOLF", "STAG", "BOAR", "BEAR", "TIGER", "SWIFTCLAW")

EN_TRANSLATIONS = {
    "ORE": "Ore",
    "WOOD": "Wood",
    "FIBER": "Fiber",
    "HIDE": "Hide",
    "ROCK": "Stone",
    "METALBAR": "Metal Bar",
    "PLANKS": "Planks",
    "CLOTH": "Cloth",
    "LEATHER": "Leather",
    "BLOCK": "Block",
    "BAG": "Bag",
    "CAPE": "Cape",
    "MOUNT": "Mount",
    "HORSE": "Horse",
    "OX": "Ox",
    "MAMMOTH": "Mammoth",
    "WOLF": "Wolf",
    "STAG": "Stag",
    "BOAR": "Boar",
    "BEAR": "Bear",
    "TIGER": "Tiger",
    "SWIFTCLAW": "Swiftclaw",
    "MAIN": "Main",
    "ARMOR": "Armor",
    "HEAD": "Head",
    "SHOES": "Shoes",
    "GATHERER": "Gatherer",
}

FR_TRANSLATIONS = {
    "ORE": "Minerai",
    "WOOD": "Bois",
    "FIBER": "Fibre",
    "HIDE": "Peau",
    "ROCK": "Pierre",
    "METALBAR": "Barre metal",
    "PLANKS": "Planches",
    "CLOTH": "Tissu",
    "LEATHER": "Cuir",
    "BLOCK": "Bloc",
    "BAG": "Sac",
    "CAPE": "Cape",
    "MOUNT": "Monture",
    "HORSE": "Cheval",
    "OX": "Boeuf",
    "MAMMOTH": "Mammouth",
    "WOLF": "Loup",
    "STAG": "Cerf",
    "BOAR": "Sanglier",
    "BEAR": "Ours",
    "TIGER": "Tigre",
    "SWIFTCLAW": "Griffe-rapide",
    "MAIN": "Arme principale",
    "ARMOR": "Armure",
    "HEAD": "Tete",
    "SHOES": "Chaussures",
    "GATHERER": "Ressourceur",
}


@dataclass(slots=True)
class CatalogItem:
    item_id: str
    name: str
    category: str
    tier: str


def batched(values: list[str], batch_size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), batch_size):
        yield values[index : index + batch_size]


def normalize_label(value: str) -> str:
    return value.replace("_", " ").replace("  ", " ").strip().title()


def format_item_name(item_id: str, language: str = "en") -> str:
    tokens = [token for token in item_id.split("_") if token]
    if not tokens:
        return item_id

    tier = tokens[0] if tokens[0].startswith("T") else ""
    words: list[str] = []
    translations = FR_TRANSLATIONS if language == "fr" else EN_TRANSLATIONS

    for token in tokens[1:]:
        upper_token = token.upper()
        if upper_token in translations:
            words.append(translations[upper_token])
        elif upper_token in {"MARTLOCK", "BRIDGEWATCH", "FORT", "STERLING", "LYMHURST", "THETFORD", "CAERLEON"}:
            words.append(token.title())
        else:
            words.append(token.replace("-", " ").title())

    if language == "fr":
        if tier:
            return f"{' '.join(words)} {tier}".strip()
        return " ".join(words).strip()

    if tier:
        return f"{tier} {' '.join(words)}".strip()
    return " ".join(words).strip()


def parse_tier(item_id: str) -> str | None:
    match = TIER_RE.match(item_id)
    if not match:
        return None
    return f"T{match.group(1)}"


def guess_category(item_id: str) -> str | None:
    upper_id = item_id.upper()
    if any(marker in upper_id for marker in BAG_MARKERS):
        return "bags"
    if any(marker in upper_id for marker in CAPE_MARKERS):
        return "capes"
    if any(marker in upper_id for marker in MOUNT_MARKERS):
        return "mounts"
    if any(marker in upper_id for marker in RESOURCE_SUFFIXES):
        return "resources"
    if any(marker in upper_id for marker in ARMOR_MARKERS):
        return "armors"
    if any(marker in upper_id for marker in WEAPON_MARKERS):
        return "weapons"
    return None


def is_equipment_category(category: str) -> bool:
    return category in {"weapons", "armors"}


def pick_first(record: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def read_remote_catalog(timeout: float = 15.0) -> list[CatalogItem]:
    session = requests.Session()
    session.headers.update({"User-Agent": "AlbionTraderPro/1.0"})
    response = session.get(REMOTE_ITEMS_URL, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict):
        records = list(payload.values())
    elif isinstance(payload, list):
        records = payload
    else:
        return []

    catalog: list[CatalogItem] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        item_id = pick_first(record, ["UniqueName", "unique_name", "item_id", "ItemId", "id"])
        if not item_id:
            continue
        item_id = str(item_id)
        tier = parse_tier(item_id)
        if tier is None:
            continue
        category = guess_category(item_id)
        if category is None and item_id.upper().startswith("T") and ("HEAD_" in item_id.upper() or "ARMOR_" in item_id.upper() or "SHOES_" in item_id.upper()):
            category = "armors"
        if category is None and ("MAIN_" in item_id.upper() or "2H_" in item_id.upper()):
            category = "weapons"
        if category is None:
            continue

        name = pick_first(record, ["LocalizedName", "localized_name", "name", "Name", "ItemName"])
        if not name:
            name = normalize_label(item_id)
        else:
            name = str(name)

        catalog.append(CatalogItem(item_id=item_id, name=name, category=category, tier=tier))

    return catalog


def fallback_catalog() -> list[CatalogItem]:
    catalog: list[CatalogItem] = []
    resource_families = ["ORE", "WOOD", "FIBER", "HIDE", "ROCK", "METALBAR", "PLANKS", "CLOTH", "LEATHER", "BLOCK"]
    for tier in TIER_OPTIONS:
        for family in resource_families:
            item_id = f"{tier}_{family}"
            catalog.append(CatalogItem(item_id=item_id, name=normalize_label(item_id), category="resources", tier=tier))
        catalog.append(CatalogItem(item_id=f"{tier}_BAG", name=normalize_label(f"{tier}_BAG"), category="bags", tier=tier))
        for city in ["MARTLOCK", "BRIDGEWATCH", "FORT_STERLING", "LYMHURST", "THETFORD", "CAERLEON"]:
            item_id = f"{tier}_CAPEITEM_{city}"
            catalog.append(CatalogItem(item_id=item_id, name=normalize_label(item_id), category="capes", tier=tier))
        for mount in ["MOUNT_HORSE", "MOUNT_OX", "MOUNT_STAG", "MOUNT_WOLF", "MOUNT_BOAR"]:
            item_id = f"{tier}_{mount}"
            catalog.append(CatalogItem(item_id=item_id, name=normalize_label(item_id), category="mounts", tier=tier))
    return catalog


def load_catalog(timeout: float = 15.0) -> list[CatalogItem]:
    try:
        remote_catalog = read_remote_catalog(timeout=timeout)
        if remote_catalog:
            LOGGER.info("Loaded %d remote Albion items", len(remote_catalog))
            return remote_catalog
    except Exception as exc:  # pragma: no cover - network fallback
        LOGGER.warning("Could not load remote item catalog: %s", exc)

    LOGGER.info("Using fallback item catalog")
    return fallback_catalog()


def filter_catalog(catalog: list[CatalogItem], selected_categories: list[str], selected_tiers: list[str]) -> list[CatalogItem]:
    category_set = set(selected_categories)
    tier_set = set(selected_tiers)
    filtered: list[CatalogItem] = []
    seen_ids: set[str] = set()

    for item in catalog:
        if item.item_id in seen_ids:
            continue
        if item.tier not in tier_set:
            continue

        allowed = False
        if item.category in category_set:
            allowed = True
        elif item.category in {"weapons", "armors"} and "equipment" in category_set:
            allowed = True
        elif item.category in {"weapons", "armors"} and item.category in category_set:
            allowed = True

        if not allowed:
            continue

        seen_ids.add(item.item_id)
        filtered.append(item)

    filtered.sort(key=lambda entry: (int(entry.tier[1:]), entry.category, entry.name))
    return filtered


def prepare_export_dataframe(dataframe):
    import pandas as pd

    if dataframe is None or dataframe.empty:
        return pd.DataFrame()
    return dataframe.copy()


def format_currency(value: float | int | None) -> str:
    if value is None:
        return "-"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{amount:,.0f}".replace(",", " ")


def format_percent(value: float | int | None) -> str:
    if value is None:
        return "-"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{amount:.2f}%"


def load_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
