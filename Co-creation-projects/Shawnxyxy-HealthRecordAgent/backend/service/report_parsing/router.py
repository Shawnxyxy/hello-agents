"""格式检测与 Extractor 路由。"""

from __future__ import annotations

from core.config import get_config
from service.report_parsing.errors import ParseError, ParseErrorCode
from service.report_parsing.extractors.base import BaseExtractor
from service.report_parsing.extractors.pdf_hybrid_extractor import PdfHybridExtractor
from service.report_parsing.extractors.txt_extractor import TxtExtractor
from service.report_parsing.schemas import DocumentArtifact

MAX_BYTES = 10 * 1024 * 1024


def detect_format(contents: bytes, filename: str | None) -> str:
    """magic bytes 优先于扩展名，避免 PDF 误标为 .txt。"""
    if contents[:4] == b"%PDF":
        return "pdf"
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".txt"):
        return "txt"
    return "unknown"


def get_extractor(fmt: str) -> BaseExtractor:
    if fmt == "txt":
        return TxtExtractor()
    if fmt == "pdf":
        return PdfHybridExtractor()
    raise ParseError(ParseErrorCode.UNSUPPORTED_FORMAT, "仅支持 .pdf 或 .txt 附件")


def _try_ocr_fallback(contents: bytes, filename: str | None) -> DocumentArtifact:
    cfg = get_config().parse
    if not cfg.ocr_enabled:
        raise ParseError(
            ParseErrorCode.OCR_UNAVAILABLE,
            "该 PDF 无文字层（可能是扫描件）。请在 .env 设置 OCR_ENABLED=true 并安装 paddleocr",
        )
    from service.report_parsing.extractors.ocr_extractor import OcrPdfExtractor

    return OcrPdfExtractor(max_pages=cfg.ocr_max_pages).extract(contents, filename)


def extract_document(contents: bytes, filename: str | None) -> DocumentArtifact:
    if len(contents) > MAX_BYTES:
        raise ParseError(ParseErrorCode.FILE_TOO_LARGE, "附件过大，请上传 10MB 以内的文件")
    if not contents:
        raise ParseError(ParseErrorCode.NO_TEXT_EXTRACTED, "文件内容为空")

    fmt = detect_format(contents, filename)
    if fmt == "unknown":
        raise ParseError(ParseErrorCode.UNSUPPORTED_FORMAT, "仅支持 .pdf 或 .txt 附件")

    artifact = get_extractor(fmt).extract(contents, filename)

    if fmt == "pdf" and not artifact.raw_text.strip() and not artifact.tables:
        artifact = _try_ocr_fallback(contents, filename)

    if not artifact.raw_text.strip() and not artifact.tables:
        raise ParseError(
            ParseErrorCode.NO_TEXT_EXTRACTED,
            "无法从文件中读取文字，请尝试 txt 或文字型 PDF",
        )
    return artifact
