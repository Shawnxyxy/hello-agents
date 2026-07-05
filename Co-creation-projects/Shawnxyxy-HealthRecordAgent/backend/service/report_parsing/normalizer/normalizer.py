"""候选指标归一化。"""

from __future__ import annotations

from typing import Dict, List

from service.report_parsing.normalizer.catalog import is_blood_pressure_label, match_canonical
from service.report_parsing.normalizer.value_parser import parse_blood_pressure, parse_numeric
from service.report_parsing.schemas import NormalizedIndicator, RawIndicatorCandidate


def normalize_candidates(candidates: List[RawIndicatorCandidate]) -> List[NormalizedIndicator]:
    out: List[NormalizedIndicator] = []
    by_code: Dict[str, NormalizedIndicator] = {}

    for cand in candidates:
        if is_blood_pressure_label(cand.name_raw):
            bp = parse_blood_pressure(cand.value_raw)
            if bp:
                sbp_val, dbp_val = bp
                for code, display, val in (
                    ("sbp", "收缩压", sbp_val),
                    ("dbp", "舒张压", dbp_val),
                ):
                    ind = NormalizedIndicator(
                        canonical_code=code,
                        display_name=display,
                        value=val,
                        normalized_value=val,
                        unit=cand.unit_raw or "mmHg",
                        status="unknown",
                        reference_range=cand.reference_range,
                        confidence=cand.confidence,
                        source=cand.source,
                    )
                    _merge_indicator(by_code, ind)
            continue

        matched = match_canonical(cand.name_raw)
        if matched:
            code, entry, conf = matched
            num = parse_numeric(cand.value_raw)
            confidence = max(cand.confidence, conf) if cand.source != "llm" else min(cand.confidence, conf)
            ind = NormalizedIndicator(
                canonical_code=code,
                display_name=str(entry.get("display_name", cand.name_raw)),
                value=cand.value_raw if num is None else num,
                normalized_value=num,
                unit=cand.unit_raw or str(entry.get("default_unit") or ""),
                status="unknown",
                reference_range=cand.reference_range,
                confidence=confidence,
                needs_review=False,
                source=cand.source,
            )
            _merge_indicator(by_code, ind)
            continue

        # 词表未命中：保留 raw 名，needs_review
        slug = f"raw_{len(by_code)}"
        num = parse_numeric(cand.value_raw)
        ind = NormalizedIndicator(
            canonical_code=slug,
            display_name=cand.name_raw,
            value=cand.value_raw if num is None else num,
            normalized_value=num,
            unit=cand.unit_raw or "",
            status="unknown",
            reference_range=cand.reference_range,
            confidence=min(cand.confidence, 0.6),
            needs_review=True,
            source=cand.source,
        )
        _merge_indicator(by_code, ind)

    out = list(by_code.values())
    return out


def _merge_indicator(store: Dict[str, NormalizedIndicator], ind: NormalizedIndicator) -> None:
    prev = store.get(ind.canonical_code)
    if prev is None or ind.confidence >= prev.confidence:
        store[ind.canonical_code] = ind
