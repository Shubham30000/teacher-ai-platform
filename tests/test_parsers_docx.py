from app.parsers.docx_parser import DocxParser


def test_docx_parser_extracts_headings(sample_docx_path):
    doc = DocxParser().parse(sample_docx_path)
    headings = [s.heading for s in doc.all_sections_flat() if s.heading]
    assert "Force and Pressure" in headings
    assert any("Introduction" in h for h in headings)
    assert any("Types of Force" in h for h in headings)


def test_docx_parser_extracts_table(sample_docx_path):
    doc = DocxParser().parse(sample_docx_path)
    assert doc.total_table_count() == 1
    table = next(s.tables[0] for s in doc.all_sections_flat() if s.tables)
    assert table.n_rows == 2
    assert table.n_cols == 2
    markdown = table.to_markdown()
    assert "Quantity" in markdown
    assert "Newton" in markdown


def test_docx_parser_extracts_list_items(sample_docx_path):
    doc = DocxParser().parse(sample_docx_path)
    all_blocks = [b for s in doc.all_sections_flat() for b in s.blocks]
    texts = [b.text for b in all_blocks]
    assert "Muscular force" in texts
    assert "Gravitational force" in texts


def test_docx_parser_metadata(sample_docx_path):
    doc = DocxParser().parse(sample_docx_path)
    assert doc.metadata.file_type.value == "docx"
    assert doc.metadata.source_filename == sample_docx_path.name
    assert doc.metadata.file_size_bytes > 0
