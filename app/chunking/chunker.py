"""
Chunking (PROJECT_ROADMAP.md item 8).

Chunks are built per-section, walking the document hierarchy so a
chunk boundary is never drawn arbitrarily mid-thought across unrelated
headings. Within a section, consecutive paragraphs/list-items/tables
are grouped up to ``chunk_max_tokens`` with a small trailing overlap
carried into the next chunk (for continuity when a concept spans a
chunk boundary), and a paragraph that is itself larger than
``chunk_max_tokens`` is split at sentence boundaries rather than cut
mid-sentence.

Token counting here is a *word-count approximation* (documented in
PHASE_1A_COMPLETION.md under Known Limitations) rather than a real
tokenizer, to avoid adding a heavyweight tokenizer dependency in
Phase 1A; it is conservative enough that real token counts for the
configured embedding model stay comfortably under its input limit.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.chunking.models import Chunk
from app.config import get_settings
from app.core.exceptions import ChunkingError
from app.document_intelligence.models import Section, StructuredDocument

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class _Item:
    text: str
    page_number: Optional[int]
    is_table: bool = False


@dataclass
class _Window:
    items: List[_Item] = field(default_factory=list)

    def token_count(self) -> int:
        return sum(_approx_token_count(item.text) for item in self.items)

    def text(self) -> str:
        return "\n".join(item.text for item in self.items)

    def has_table(self) -> bool:
        return any(item.is_table for item in self.items)

    def first_page(self) -> Optional[int]:
        for item in self.items:
            if item.page_number is not None:
                return item.page_number
        return None


def _approx_token_count(text: str) -> int:
    return max(1, len(text.split()))


class EducationalChunker:
    """Splits a StructuredDocument into pedagogically-coherent Chunks."""

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None,
        min_tokens: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.max_tokens = max_tokens or settings.chunk_max_tokens
        self.overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens
        self.min_tokens = min_tokens or settings.chunk_min_tokens
        if self.overlap_tokens >= self.max_tokens:
            raise ChunkingError("chunk_overlap_tokens must be smaller than chunk_max_tokens")

    def chunk_document(self, document: StructuredDocument) -> List[Chunk]:
        if not document.sections:
            logger.warning("Document %s has no sections to chunk", document.document_id)
            return []

        chunks: List[Chunk] = []
        counter = {"index": 0}
        for section in document.sections:
            self._chunk_section_recursive(document, section, [], chunks, counter)

        logger.info(
            "Chunked document %s into %d chunks (max=%d, overlap=%d, min=%d)",
            document.document_id, len(chunks), self.max_tokens, self.overlap_tokens, self.min_tokens,
        )
        return chunks

    # -- internals ------------------------------------------------------

    def _chunk_section_recursive(
        self,
        document: StructuredDocument,
        section: Section,
        parent_heading_path: List[str],
        out: List[Chunk],
        counter: dict,
    ) -> None:
        heading_path = parent_heading_path + ([section.heading] if section.heading else [])

        items = self._section_items(section)
        if items:
            for window in self._window_items(items):
                chunk = self._window_to_chunk(document, section, heading_path, window, counter)
                out.append(chunk)

        for subsection in section.subsections:
            self._chunk_section_recursive(document, subsection, heading_path, out, counter)

    @staticmethod
    def _section_items(section: Section) -> List[_Item]:
        items: List[_Item] = []
        for block in section.blocks:
            if block.text.strip():
                items.append(_Item(text=block.text.strip(), page_number=block.page_number))
        for table in section.tables:
            markdown = table.to_markdown()
            if markdown.strip():
                items.append(
                    _Item(text=markdown, page_number=table.page_number, is_table=True)
                )
        return items

    def _window_items(self, items: List[_Item]) -> List[_Window]:
        # Pre-split any oversized single item at sentence boundaries.
        normalized: List[_Item] = []
        for item in items:
            if _approx_token_count(item.text) <= self.max_tokens or item.is_table:
                normalized.append(item)
                continue
            for piece in self._split_oversized(item.text):
                normalized.append(_Item(text=piece, page_number=item.page_number))

        windows: List[_Window] = []
        current = _Window()
        for item in normalized:
            item_tokens = _approx_token_count(item.text)
            if current.items and current.token_count() + item_tokens > self.max_tokens:
                windows.append(current)
                current = _Window(items=self._carry_overlap(current))
            current.items.append(item)
        if current.items:
            windows.append(current)
        return windows

    def _carry_overlap(self, window: _Window) -> List[_Item]:
        if self.overlap_tokens <= 0:
            return []
        carried: List[_Item] = []
        running = 0
        for item in reversed(window.items):
            tokens = _approx_token_count(item.text)
            if running + tokens > self.overlap_tokens:
                break
            carried.insert(0, item)
            running += tokens
        return carried

    def _split_oversized(self, text: str) -> List[str]:
        sentences = _SENTENCE_SPLIT_RE.split(text)
        pieces: List[str] = []
        current: List[str] = []
        current_tokens = 0
        for sentence in sentences:
            tokens = _approx_token_count(sentence)
            if current and current_tokens + tokens > self.max_tokens:
                pieces.append(" ".join(current))
                current, current_tokens = [], 0
            current.append(sentence)
            current_tokens += tokens
        if current:
            pieces.append(" ".join(current))
        return pieces or [text]

    def _window_to_chunk(
        self,
        document: StructuredDocument,
        section: Section,
        heading_path: List[str],
        window: _Window,
        counter: dict,
    ) -> Chunk:
        chunk = Chunk(
            document_id=document.document_id,
            section_id=section.section_id,
            chunk_index=counter["index"],
            heading_path=heading_path,
            text=window.text(),
            approx_token_count=window.token_count(),
            page_number=window.first_page() or section.page_number,
            contains_table=window.has_table(),
            contains_image_reference=bool(section.images),
            source_filename=document.metadata.source_filename,
        )
        counter["index"] += 1
        return chunk
