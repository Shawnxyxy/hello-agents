"""数值与单位解析。"""

from __future__ import annotations

import re
from typing import Optional, Tuple


def parse_numeric(value_raw: str) -> Optional[float]:
    if value_raw is None:
        return None
    text = str(value_raw).strip()
    if not text:
        return None
    numbers = re.findall(r"[-+]?\d*\.?\d+", text.replace(",", ""))
    if not numbers:
        return None
    try:
        return float(numbers[0])
    except ValueError:
        return None


def parse_blood_pressure(value_raw: str) -> Optional[Tuple[float, float]]:
    m = re.search(r"(\d{2,3})\s*[/／]\s*(\d{2,3})", str(value_raw))
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def infer_status(value: Optional[float], plausible_range: Optional[list]) -> str:
    if value is None or not plausible_range or len(plausible_range) != 2:
        return "unknown"
    lo, hi = plausible_range
    if value < lo:
        return "low"
    if value > hi:
        return "high"
    return "normal"
