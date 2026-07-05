"""解析结果校验。"""

from __future__ import annotations

from typing import List

from service.report_parsing.normalizer.catalog import load_catalog
from service.report_parsing.normalizer.value_parser import infer_status
from service.report_parsing.quality import compute_parse_quality
from service.report_parsing.schemas import NormalizedIndicator, ParseQuality


def validate_indicators(
    indicators: List[NormalizedIndicator],
    warnings: List[str],
    *,
    text_coverage: float = 1.0,
    extraction_method: str = "pipeline",
) -> tuple[List[NormalizedIndicator], ParseQuality]:
    catalog = load_catalog()
    validated: List[NormalizedIndicator] = []

    for ind in indicators:
        entry = catalog.get(ind.canonical_code, {})
        pr = entry.get("plausible_range")
        if pr and ind.normalized_value is not None:
            status = infer_status(ind.normalized_value, pr)
            if status != "unknown":
                ind = ind.model_copy(update={"status": status})
            lo, hi = pr
            if ind.normalized_value < lo * 0.5 or ind.normalized_value > hi * 2:
                warnings.append(f"{ind.display_name} 数值异常，建议核对")
                ind = ind.model_copy(update={"needs_review": True, "confidence": min(ind.confidence, 0.5)})
        validated.append(ind)

    quality = compute_parse_quality(
        validated,
        warnings,
        text_coverage=text_coverage,
        extraction_method=extraction_method,
    )
    return validated, quality
