"""指标词表加载与匹配。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

_CATALOG_PATH = Path(__file__).with_name("indicator_catalog.yaml")
_MIN_FUZZY_ALIAS_LEN = 4


@lru_cache(maxsize=1)
def load_catalog() -> Dict[str, Dict[str, Any]]:
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _normalize_key(text: str) -> str:
    return text.strip().lower().replace(" ", "").replace("（", "(").replace("）", ")")


def _alias_matches(key: str, alias: str) -> bool:
    if not alias:
        return False
    if key == alias:
        return True
    if len(alias) < _MIN_FUZZY_ALIAS_LEN:
        return False
    return alias in key


def match_canonical(name_raw: str) -> Optional[Tuple[str, Dict[str, Any], float]]:
    """词表匹配，返回 (canonical_code, entry, confidence)。"""
    key = _normalize_key(name_raw)
    if not key:
        return None

    catalog = load_catalog()
    for code, entry in catalog.items():
        if entry.get("split_pair"):
            continue
        display = _normalize_key(entry.get("display_name", ""))
        aliases = [_normalize_key(a) for a in entry.get("aliases", [])]
        if key == display or key in aliases:
            return code, entry, 0.92
        for alias in aliases:
            if _alias_matches(key, alias):
                return code, entry, 0.85
    return None


def is_blood_pressure_label(name_raw: str) -> bool:
    key = _normalize_key(name_raw)
    entry = load_catalog().get("blood_pressure", {})
    aliases = [_normalize_key(a) for a in entry.get("aliases", [])]
    return key in aliases or key == _normalize_key(entry.get("display_name", ""))
