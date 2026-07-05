"""OCR Extractor — PaddleOCR optional，用于扫描 PDF。"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import List

import pdfplumber

from service.report_parsing.errors import ParseError, ParseErrorCode
from service.report_parsing.extractors.base import BaseExtractor
from service.report_parsing.schemas import DocumentArtifact

logger = logging.getLogger(__name__)

_ocr_engine = None


def is_paddleocr_available() -> bool:
    try:
        import paddleocr  # noqa: F401

        return True
    except ImportError:
        return False


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise ParseError(
                ParseErrorCode.OCR_UNAVAILABLE,
                "未安装 PaddleOCR，请执行: pip install paddleocr paddlepaddle",
            ) from exc
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    return _ocr_engine


def _ocr_page_image(pil_image) -> str:
    import numpy as np

    ocr = _get_ocr_engine()
    arr = np.array(pil_image.convert("RGB"))
    result = ocr.ocr(arr, cls=True)
    lines: List[str] = []
    if result and result[0]:
        for line in result[0]:
            if line and len(line) >= 2 and line[1]:
                text = line[1][0]
                if text:
                    lines.append(str(text))
    return "\n".join(lines)


class OcrPdfExtractor(BaseExtractor):
    """将 PDF 每页渲染为图片后 OCR。"""

    def __init__(self, max_pages: int = 5):
        self.max_pages = max_pages

    def extract(self, contents: bytes, filename: str | None) -> DocumentArtifact:
        if not is_paddleocr_available():
            raise ParseError(
                ParseErrorCode.OCR_UNAVAILABLE,
                "未安装 PaddleOCR，请执行: pip install paddleocr paddlepaddle",
            )

        text_parts: list[str] = []
        page_count = 0
        warnings: list[str] = []

        try:
            with pdfplumber.open(BytesIO(contents)) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages[: self.max_pages]:
                    try:
                        img = page.to_image(resolution=150).original
                        page_text = _ocr_page_image(img)
                        if page_text.strip():
                            text_parts.append(page_text)
                    except Exception as exc:
                        logger.warning("OCR 单页失败: %s", exc)
                        warnings.append(f"第 {page.page_number} 页 OCR 失败")
        except Exception as exc:
            raise ParseError(ParseErrorCode.PDF_CORRUPT, f"PDF 渲染失败: {exc}") from exc

        if page_count > self.max_pages:
            warnings.append(f"仅 OCR 前 {self.max_pages} 页（共 {page_count} 页）")

        raw = "\n".join(text_parts).strip()
        if not raw:
            raise ParseError(
                ParseErrorCode.NO_TEXT_EXTRACTED,
                "OCR 未能识别出文字，请尝试更清晰的扫描件或文字版 PDF",
            )

        coverage = min(1.0, len(raw) / 400.0)
        return DocumentArtifact(
            source_filename=filename,
            source_format="pdf_scanned",
            raw_text=raw,
            tables=[],
            page_count=page_count,
            extraction_method="paddleocr",
            quality_score=coverage * 0.85,
            warnings=warnings,
        )
