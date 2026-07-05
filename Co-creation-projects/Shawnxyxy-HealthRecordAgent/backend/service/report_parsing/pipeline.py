"""报告解析主流水线。"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Optional

from service.report_parsing.errors import ParseError, ParseErrorCode
from service.report_parsing.normalizer.normalizer import normalize_candidates
from service.report_parsing.router import extract_document
from service.report_parsing.schemas import DocumentArtifact, ParsedReport
from service.report_parsing.structurer.llm_structurer import llm_enrich_candidates
from service.report_parsing.structurer.rule_structurer import rule_structure
from service.report_parsing.validator.parse_validator import validate_indicators


class ReportParsingPipeline:
    """文件/文本 → ParsedReport。"""

    def ingest_bytes(self, contents: bytes, filename: Optional[str] = None) -> ParsedReport:
        """同步入口（仅 pytest/脚本；勿在已有 event loop 内调用）。"""
        return asyncio.run(self.ingest_bytes_async(contents, filename, skip_llm=True))

    def ingest_text(self, text: str, filename: Optional[str] = "report.txt") -> ParsedReport:
        """同步入口（仅 pytest/脚本；勿在已有 event loop 内调用）。"""
        return asyncio.run(self.ingest_text_async(text, filename, skip_llm=True))

    async def ingest_bytes_async(
        self, contents: bytes, filename: Optional[str] = None, *, skip_llm: bool = False
    ) -> ParsedReport:
        artifact = await asyncio.to_thread(extract_document, contents, filename)
        return await self._structure_async(artifact, skip_llm=skip_llm)

    async def ingest_text_async(
        self, text: str, filename: Optional[str] = "report.txt", *, skip_llm: bool = False
    ) -> ParsedReport:
        raw = (text or "").strip()
        if not raw:
            raise ParseError(ParseErrorCode.NO_TEXT_EXTRACTED, "报告文本为空")
        artifact = DocumentArtifact(
            source_filename=filename,
            source_format="txt",
            raw_text=raw,
            extraction_method="direct_text",
            quality_score=min(1.0, len(raw) / 400.0),
        )
        return await self._structure_async(artifact, skip_llm=skip_llm)

    async def _structure_async(
        self, artifact: DocumentArtifact, *, skip_llm: bool = False
    ) -> ParsedReport:
        candidates, patient, warnings = rule_structure(artifact)
        llm_added, llm_failed, llm_err = await llm_enrich_candidates(
            artifact.raw_text, candidates, skip_llm=skip_llm
        )
        candidates.extend(llm_added)
        if llm_failed:
            warnings.append("LLM 补全失败，已保留规则提取结果")
            if llm_err:
                warnings.append(llm_err[:120])

        indicators = normalize_candidates(candidates)
        text_coverage = min(1.0, artifact.quality_score or (1.0 if artifact.raw_text else 0.0))
        indicators, quality = validate_indicators(
            indicators,
            warnings,
            text_coverage=text_coverage,
            extraction_method=artifact.extraction_method,
        )

        if quality.indicator_count == 0:
            quality.degraded = True
            if ParseErrorCode.ZERO_INDICATORS.value not in quality.warnings:
                quality.warnings.append(ParseErrorCode.ZERO_INDICATORS.value)

        text_hash = hashlib.sha256(artifact.raw_text.encode("utf-8", errors="replace")).hexdigest()[:16]
        return ParsedReport(
            artifact=artifact,
            patient=patient,
            indicators=indicators,
            quality=quality,
            raw_text_hash=text_hash,
        )
