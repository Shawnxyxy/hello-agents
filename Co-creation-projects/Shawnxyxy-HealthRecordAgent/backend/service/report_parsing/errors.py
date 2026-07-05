"""报告解析错误码。"""

from __future__ import annotations

from enum import Enum


class ParseErrorCode(str, Enum):
    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    PDF_CORRUPT = "pdf_corrupt"
    NO_TEXT_EXTRACTED = "no_text_extracted"
    OCR_UNAVAILABLE = "ocr_unavailable"
    LLM_STRUCT_FAILED = "llm_struct_failed"
    ZERO_INDICATORS = "zero_indicators"


class ParseError(Exception):
    def __init__(self, code: ParseErrorCode, message: str):
        self.code = code
        super().__init__(message)
