from app.document_intelligence.models import (
    ContentBlock,
    DocumentMetadata,
    HeadingLevel,
    Section,
    StructuredDocument,
    TableCell,
    TableElement,
)


def _sample_document() -> StructuredDocument:
    sub = Section(heading="1.1 Sub", heading_level=HeadingLevel.H2)
    sub.blocks.append(ContentBlock(text="Subsection text"))
    top = Section(heading="1. Top", heading_level=HeadingLevel.H1)
    top.blocks.append(ContentBlock(text="Top-level text"))
    top.subsections.append(sub)
    return StructuredDocument(
        metadata=DocumentMetadata(source_filename="x.txt"),
        sections=[top],
    )


def test_full_text_includes_all_nested_content():
    doc = _sample_document()
    text = doc.full_text()
    assert "Top-level text" in text
    assert "Subsection text" in text


def test_all_sections_flat_returns_depth_first():
    doc = _sample_document()
    flat = doc.all_sections_flat()
    assert [s.heading for s in flat] == ["1. Top", "1.1 Sub"]


def test_table_to_markdown():
    table = TableElement(
        n_rows=2,
        n_cols=2,
        cells=[
            TableCell(text="A", row=0, col=0, is_header=True),
            TableCell(text="B", row=0, col=1, is_header=True),
            TableCell(text="1", row=1, col=0),
            TableCell(text="2", row=1, col=1),
        ],
    )
    markdown = table.to_markdown()
    assert markdown.startswith("| A | B |")
    assert "| 1 | 2 |" in markdown


def test_total_table_and_image_counts():
    doc = _sample_document()
    doc.sections[0].tables.append(TableElement(n_rows=1, n_cols=1, cells=[]))
    assert doc.total_table_count() == 1
    assert doc.total_image_count() == 0
