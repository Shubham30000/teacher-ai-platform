"""Models for educationally-meaningful chunks produced from a StructuredDocument."""
from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """
    One retrievable unit of content.

    ``heading_path`` preserves the section hierarchy the chunk came
    from (e.g. ``["Chapter 8: Force and Pressure", "8.2 Pressure"]``)
    so that retrieval results carry pedagogical context, not just raw
    text - this is what lets a downstream lesson planner know *where*
    in the chapter a fact came from.
    """

    chunk_id: str = Field(default_factory=lambda: uuid4().hex)
    document_id: str
    section_id: str
    chunk_index: int
    heading_path: List[str] = Field(default_factory=list)
    text: str
    approx_token_count: int
    page_number: Optional[int] = None
    contains_table: bool = False
    contains_image_reference: bool = False
    source_filename: Optional[str] = None

    def to_metadata_dict(self) -> dict:
        """Flat, Chroma-compatible metadata (Chroma metadata values must be scalars)."""
        return {
            "document_id": self.document_id,
            "section_id": self.section_id,
            "chunk_index": self.chunk_index,
            "heading_path": " > ".join(self.heading_path) if self.heading_path else "",
            "page_number": self.page_number if self.page_number is not None else -1,
            "contains_table": self.contains_table,
            "contains_image_reference": self.contains_image_reference,
            "source_filename": self.source_filename or "",
        }
