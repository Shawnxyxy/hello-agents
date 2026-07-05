"""纯文本 Extractor。"""

from __future__ import annotations

from service.report_parsing.errors import ParseError, ParseErrorCode
from service.report_parsing.extractors.base import BaseExtractor
from service.report_parsing.schemas import DocumentArtifact


def _is_likely_binary_gibberish(text: str) -> bool:
    """检测误标扩展名的二进制内容（如 PDF 改名为 .txt）。"""
    if not text:
        return False
    sample = text[:4000]
    if not sample:
        return False
    control = sum(1 for c in sample if ord(c) < 9 or (13 < ord(c) < 32))
    if len(sample) > 80 and control / len(sample) > 0.12:
        return True
    if sample.count("\ufffd") / len(sample) > 0.05:
        return True
    if sample.lstrip().startswith("%PDF"):
        return True
    return False


class TxtExtractor(BaseExtractor):
    def extract(self, contents: bytes, filename: str | None) -> DocumentArtifact:
        text = ""
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                text = contents.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not text:
            text = contents.decode("utf-8", errors="replace")

        if _is_likely_binary_gibberish(text):
            raise ParseError(
                ParseErrorCode.UNSUPPORTED_FORMAT,
                "文件内容不像文本报告，请确认扩展名（PDF 请使用 .pdf）",
            )

        raw = text.strip()
        coverage = min(1.0, len(raw) / 400.0) if raw else 0.0
        return DocumentArtifact(
            source_filename=filename,
            source_format="txt",
            raw_text=raw,
            extraction_method="txt_decode",
            quality_score=coverage,
        )
