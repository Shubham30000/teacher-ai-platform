"""Shared enums and constants used across modules."""
from enum import Enum


class InputMode(str, Enum):
    """How the ingestion pipeline was triggered."""

    FILE_UPLOAD = "file_upload"


class SupportedFileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    TXT = "txt"


EXTENSION_TO_FILE_TYPE = {
    ".pdf": SupportedFileType.PDF,
    ".docx": SupportedFileType.DOCX,
    ".pptx": SupportedFileType.PPTX,
    ".txt": SupportedFileType.TXT,
}


class ElementType(str, Enum):
    """Structural element types preserved by every parser."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"
    LIST_ITEM = "list_item"
    URL = "url"
    SLIDE = "slide"
    CAPTION = "caption"


class JobStage(str, Enum):
    """Stages reported by the progress-streaming API for Phase 1A."""

    QUEUED = "queued"
    ROUTING = "routing"
    PARSING = "parsing"
    STRUCTURING = "structuring"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    CLASSIFYING = "classifying"
    EXTRACTING_KNOWLEDGE = "extracting_knowledge"
    GENERATING_PACKAGE = "generating_package"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_STAGES = {JobStage.COMPLETED, JobStage.FAILED}
