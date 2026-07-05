"""Extractor 基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from service.report_parsing.schemas import DocumentArtifact


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, contents: bytes, filename: str | None) -> DocumentArtifact:
        ...
