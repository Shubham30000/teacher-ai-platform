from app.chunking.chunker import EducationalChunker
from app.document_intelligence.models import (
    ContentBlock,
    DocumentMetadata,
    HeadingLevel,
    Section,
    StructuredDocument,
    TableCell,
    TableElement,
)


def _long_paragraph(n_words: int, prefix: str) -> str:
    return " ".join(f"{prefix}word{i}." for i in range(n_words))


def _build_document() -> StructuredDocument:
    intro = Section(heading="1. Introduction", heading_level=HeadingLevel.H1)
    intro.blocks.append(ContentBlock(text=_long_paragraph(30, "intro")))
    sub = Section(heading="1.1 Types of Force", heading_level=HeadingLevel.H2)
    sub.blocks.append(ContentBlock(text=_long_paragraph(600, "force")))
    sub.tables.append(
        TableElement(
            n_rows=1, n_cols=2,
            cells=[TableCell(text="Force", row=0, col=0), TableCell(text="Newton", row=0, col=1)],
        )
    )
    intro.subsections.append(sub)
    return StructuredDocument(metadata=DocumentMetadata(source_filename="x.txt"), sections=[intro])


def test_chunker_produces_chunks_for_every_section_with_content():
    doc = _build_document()
    chunker = EducationalChunker(max_tokens=100, overlap_tokens=10, min_tokens=5)
    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 2  # intro fits in one chunk, the 600-word section must split

    heading_paths = {tuple(c.heading_path) for c in chunks}
    assert ("1. Introduction",) in heading_paths
    assert any("1.1 Types of Force" in path for path in heading_paths)


def test_chunker_respects_max_tokens():
    doc = _build_document()
    chunker = EducationalChunker(max_tokens=100, overlap_tokens=10, min_tokens=5)
    chunks = chunker.chunk_document(doc)
    for chunk in chunks:
        # Allow a little slack: a table markdown block can push slightly over.
        assert chunk.approx_token_count <= 140, chunk.approx_token_count


def test_chunker_chunk_index_is_sequential():
    doc = _build_document()
    chunker = EducationalChunker(max_tokens=100, overlap_tokens=10, min_tokens=5)
    chunks = chunker.chunk_document(doc)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_chunker_marks_table_containing_chunks():
    doc = _build_document()
    chunker = EducationalChunker(max_tokens=50, overlap_tokens=5, min_tokens=5)
    chunks = chunker.chunk_document(doc)
    assert any(c.contains_table for c in chunks)


def test_chunker_empty_document_returns_no_chunks():
    doc = StructuredDocument(metadata=DocumentMetadata(source_filename="empty.txt"), sections=[])
    chunker = EducationalChunker()
    assert chunker.chunk_document(doc) == []


def test_chunker_rejects_invalid_overlap():
    import pytest
    from app.core.exceptions import ChunkingError

    with pytest.raises(ChunkingError):
        EducationalChunker(max_tokens=50, overlap_tokens=50)
