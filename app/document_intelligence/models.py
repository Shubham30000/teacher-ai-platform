"""
Normalized document representation.

Every parser (PDF, DOCX, PPTX, TXT) produces exactly one
``StructuredDocument``, regardless of source format. This is the
contract referenced throughout PROJECT_ROADMAP.md item 7
("Document Intelligence") - downstream stages (chunking, embedding,
retrieval) depend only on this model and never on format-specific
parser internals.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.constants import ElementType, SupportedFileType


class HeadingLevel(int, Enum):
    """Normalized heading depth. TITLE is the document/chapter title."""

    TITLE = 0
    H1 = 1
    H2 = 2
    H3 = 3
    H4 = 4


class TableCell(BaseModel):
    text: str = ""
    row: int
    col: int
    is_header: bool = False


class TableElement(BaseModel):
    element_id: str = Field(default_factory=lambda: uuid4().hex)
    type: ElementType = ElementType.TABLE
    caption: Optional[str] = None
    n_rows: int
    n_cols: int
    cells: List[TableCell] = Field(default_factory=list)
    page_number: Optional[int] = None

    def to_markdown(self) -> str:
        """Render the table as GitHub-flavored markdown for embedding/LLM consumption."""
        if self.n_rows == 0 or self.n_cols == 0:
            return ""
        grid = [["" for _ in range(self.n_cols)] for _ in range(self.n_rows)]
        for cell in self.cells:
            if 0 <= cell.row < self.n_rows and 0 <= cell.col < self.n_cols:
                grid[cell.row][cell.col] = cell.text.replace("\n", " ").strip()
        lines = ["| " + " | ".join(grid[0]) + " |"]
        lines.append("| " + " | ".join(["---"] * self.n_cols) + " |")
        for row in grid[1:]:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)


class ImageElement(BaseModel):
    element_id: str = Field(default_factory=lambda: uuid4().hex)
    type: ElementType = ElementType.IMAGE
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    page_number: Optional[int] = None
    stored_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class UrlElement(BaseModel):
    element_id: str = Field(default_factory=lambda: uuid4().hex)
    type: ElementType = ElementType.URL
    url: str
    anchor_text: Optional[str] = None
    page_number: Optional[int] = None


class ContentBlock(BaseModel):
    """A single piece of textual content within a section (paragraph or list item)."""

    element_id: str = Field(default_factory=lambda: uuid4().hex)
    type: ElementType = ElementType.PARAGRAPH
    text: str
    page_number: Optional[int] = None
    list_level: Optional[int] = None


class Section(BaseModel):
    """
    A structural unit of the document, headed by a heading of some level.

    Sections nest via ``subsections`` so that hierarchy (Chapter > Section
    > Subsection) is preserved rather than flattened, per the roadmap's
    explicit requirement to preserve "Headings / Subheadings ... Document
    hierarchy".
    """

    section_id: str = Field(default_factory=lambda: uuid4().hex)
    heading: Optional[str] = None
    heading_level: HeadingLevel = HeadingLevel.H1
    page_number: Optional[int] = None
    blocks: List[ContentBlock] = Field(default_factory=list)
    tables: List[TableElement] = Field(default_factory=list)
    images: List[ImageElement] = Field(default_factory=list)
    urls: List[UrlElement] = Field(default_factory=list)
    subsections: List["Section"] = Field(default_factory=list)

    def full_text(self, include_subsections: bool = True) -> str:
        """Flatten this section's own text (and optionally its subsections') for chunking."""
        parts: List[str] = []
        if self.heading:
            parts.append(self.heading)
        parts.extend(block.text for block in self.blocks)
        parts.extend(table.to_markdown() for table in self.tables)
        if include_subsections:
            for sub in self.subsections:
                parts.append(sub.full_text(include_subsections=True))
        return "\n".join(p for p in parts if p and p.strip())

    def iter_sections(self):
        """Depth-first iterator over this section and all descendants."""
        yield self
        for sub in self.subsections:
            yield from sub.iter_sections()


Section.model_rebuild()


class DocumentMetadata(BaseModel):
    """Metadata captured about the source document, independent of its content."""

    source_filename: Optional[str] = None
    file_type: Optional[SupportedFileType] = None
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    slide_count: Optional[int] = None
    author: Optional[str] = None
    title: Optional[str] = None
    language: Optional[str] = None
    source_url: Optional[str] = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extra: dict = Field(default_factory=dict)


class StructuredDocument(BaseModel):
    """
    The normalized output of every parser.

    ``document_id`` is stable and referenced by downstream chunks so
    that retrieval results can always be traced back to their source
    document and page/slide.
    """

    document_id: str = Field(default_factory=lambda: uuid4().hex)
    metadata: DocumentMetadata
    sections: List[Section] = Field(default_factory=list)
    raw_text_fallback: Optional[str] = None

    def full_text(self) -> str:
        return "\n\n".join(section.full_text() for section in self.sections)

    def all_sections_flat(self) -> List[Section]:
        """All sections and subsections, depth-first, as a flat list."""
        flat: List[Section] = []
        for section in self.sections:
            flat.extend(section.iter_sections())
        return flat

    def total_table_count(self) -> int:
        return sum(len(s.tables) for s in self.all_sections_flat())

    def total_image_count(self) -> int:
        return sum(len(s.images) for s in self.all_sections_flat())
