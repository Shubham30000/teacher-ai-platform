"""Abstract base class every document parser must implement."""
from __future__ import annotations

import abc
from pathlib import Path

from app.document_intelligence.models import StructuredDocument


class BaseParser(abc.ABC):
    """
    Every concrete parser must accept a file path and return a
    :class:`StructuredDocument`. This is the single contract that lets
    ``ParserFactory`` and everything downstream treat all formats
    identically (roadmap item 7: "Every parser should produce exactly
    the same structure").
    """

    #: Set by subclasses; used for logging/diagnostics only.
    format_name: str = "unknown"

    #: Whether this parser can currently handle scanned/image-only content.
    #: Phase 1A explicitly does not implement OCR - this flag lets the
    #: routing layer make that limitation visible instead of silently
    #: returning an empty document.
    supports_ocr: bool = False

    @abc.abstractmethod
    def parse(self, file_path: Path) -> StructuredDocument:
        """Parse ``file_path`` and return a normalized StructuredDocument."""
        raise NotImplementedError

    def _base_check(self, file_path: Path) -> None:
        from app.core.exceptions import ParsingError

        if not file_path.exists():
            raise ParsingError(f"File not found: {file_path}")
        if file_path.stat().st_size == 0:
            raise ParsingError(f"File is empty: {file_path}")
