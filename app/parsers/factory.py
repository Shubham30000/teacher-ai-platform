"""Maps a file extension to the parser responsible for it."""
from __future__ import annotations

from pathlib import Path

from app.core.constants import EXTENSION_TO_FILE_TYPE, SupportedFileType
from app.core.exceptions import UnsupportedFileTypeError
from app.parsers.base import BaseParser
from app.parsers.docx_parser import DocxParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.pptx_parser import PptxParser
from app.parsers.txt_parser import TxtParser


class ParserFactory:
    """Resolves the correct :class:`BaseParser` implementation for a file."""

    _REGISTRY: dict[SupportedFileType, type[BaseParser]] = {
        SupportedFileType.PDF: PdfParser,
        SupportedFileType.DOCX: DocxParser,
        SupportedFileType.PPTX: PptxParser,
        SupportedFileType.TXT: TxtParser,
    }

    @classmethod
    def get_parser(cls, file_path: Path) -> BaseParser:
        extension = file_path.suffix.lower()
        file_type = EXTENSION_TO_FILE_TYPE.get(extension)
        if file_type is None:
            raise UnsupportedFileTypeError(
                f"Unsupported file extension '{extension}'. "
                f"Supported: {', '.join(EXTENSION_TO_FILE_TYPE)}"
            )
        parser_cls = cls._REGISTRY[file_type]
        return parser_cls()

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return list(EXTENSION_TO_FILE_TYPE.keys())
