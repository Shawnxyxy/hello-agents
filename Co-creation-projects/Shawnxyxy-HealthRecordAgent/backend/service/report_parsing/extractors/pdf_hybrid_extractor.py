"""PDF 文字层 + 表格 Extractor。"""

from __future__ import annotations

from io import BytesIO

import pdfplumber

from service.report_parsing.errors import ParseError, ParseErrorCode
from service.report_parsing.extractors.base import BaseExtractor
from service.report_parsing.schemas import DocumentArtifact


class PdfHybridExtractor(BaseExtractor):
    def extract(self, contents: bytes, filename: str | None) -> DocumentArtifact:
        warnings: list[str] = []
        try:
            with pdfplumber.open(BytesIO(contents)) as pdf:
                text_parts: list[str] = []
                tables: list[list[list[str]]] = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                    page_tables = page.extract_tables() or []
                    for tbl in page_tables:
                        cleaned = [
                            [str(c or "").strip() for c in row]
                            for row in tbl
                            if row and any(str(c or "").strip() for c in row)
                        ]
                        if cleaned:
                            tables.append(cleaned)

                raw = "\n".join(text_parts).strip()
                page_count = len(pdf.pages)
        except Exception as exc:
            raise ParseError(ParseErrorCode.PDF_CORRUPT, f"无法解析 PDF: {exc}") from exc

        if not raw:
            return DocumentArtifact(
                source_filename=filename,
                source_format="pdf_scanned",
                raw_text="",
                tables=tables,
                page_count=page_count,
                extraction_method="pdfplumber_empty",
                quality_score=0.1,
                warnings=["无法从 PDF 提取文字层，可能是扫描件（可开启 OCR_ENABLED 使用 PaddleOCR）"],
            )

        coverage = min(1.0, len(raw) / 400.0)
        if tables:
            coverage = min(1.0, coverage + 0.15)

        return DocumentArtifact(
            source_filename=filename,
            source_format="pdf_text",
            raw_text=raw,
            tables=tables,
            page_count=page_count,
            extraction_method="pdfplumber_text+tables",
            quality_score=coverage,
            warnings=warnings,
        )
