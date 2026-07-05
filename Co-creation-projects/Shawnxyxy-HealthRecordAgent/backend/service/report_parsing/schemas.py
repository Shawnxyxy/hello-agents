"""报告解析 Pydantic 模型。"""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class DocumentArtifact(BaseModel):
    source_filename: Optional[str] = None
    source_format: Literal["txt", "pdf_text", "pdf_scanned", "unknown"] = "unknown"
    raw_text: str = ""
    tables: List[List[List[str]]] = Field(default_factory=list)
    page_count: int = 0
    extraction_method: str = "unknown"
    quality_score: float = 0.0
    warnings: List[str] = Field(default_factory=list)


class RawIndicatorCandidate(BaseModel):
    name_raw: str
    value_raw: str
    unit_raw: Optional[str] = None
    reference_range: Optional[str] = None
    source: Literal["table", "regex", "llm", "merged"] = "regex"
    confidence: float = 0.8
    line_context: str = ""


class NormalizedIndicator(BaseModel):
    canonical_code: str
    display_name: str
    value: Any = None
    normalized_value: Optional[float] = None
    unit: str = ""
    status: str = "unknown"
    reference_range: Optional[str] = None
    confidence: float = 0.8
    needs_review: bool = False
    source: str = "regex"


class PatientMeta(BaseModel):
    name: Optional[str] = None
    sex: Optional[str] = None
    age: Optional[int] = None
    exam_date: Optional[str] = None


class ParseQuality(BaseModel):
    overall_score: float = 0.0
    text_coverage: float = 0.0
    indicator_count: int = 0
    low_confidence_count: int = 0
    extraction_method: str = "unknown"
    degraded: bool = False
    warnings: List[str] = Field(default_factory=list)


class ParsedReport(BaseModel):
    schema_version: str = "1.0"
    artifact: DocumentArtifact
    patient: Optional[PatientMeta] = None
    indicators: List[NormalizedIndicator] = Field(default_factory=list)
    quality: ParseQuality
    raw_text_hash: str = ""

    def to_agent_indicators(self) -> List[dict]:
        """转为 HealthIndicatorAgent / ReportAgent 使用的指标列表。"""
        out: List[dict] = []
        for ind in self.indicators:
            out.append(
                {
                    "name": ind.display_name,
                    "canonical_code": ind.canonical_code,
                    "value": ind.value,
                    "normalized_value": ind.normalized_value,
                    "unit": ind.unit,
                    "status": ind.status,
                    "confidence": ind.confidence,
                    "needs_review": ind.needs_review,
                    "source": ind.source,
                }
            )
        return out
