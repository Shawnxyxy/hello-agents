"""解析质量分计算。"""

from __future__ import annotations

from typing import List

from service.report_parsing.schemas import NormalizedIndicator, ParseQuality


def compute_parse_quality(
    indicators: List[NormalizedIndicator],
    warnings: List[str],
    *,
    text_coverage: float,
    extraction_method: str,
) -> ParseQuality:
    count = len(indicators)
    avg_conf = sum(i.confidence for i in indicators) / count if count else 0.0
    low_conf = sum(1 for i in indicators if i.confidence < 0.7 or i.needs_review)
    coverage = min(1.0, max(0.0, text_coverage))
    overall = 0.4 * coverage + 0.4 * min(count / 8.0, 1.0) + 0.2 * avg_conf
    degraded = overall < 0.45 or count == 0

    return ParseQuality(
        overall_score=round(overall, 3),
        text_coverage=round(coverage, 3),
        indicator_count=count,
        low_confidence_count=low_conf,
        extraction_method=extraction_method,
        degraded=degraded,
        warnings=list(dict.fromkeys(warnings)),
    )
