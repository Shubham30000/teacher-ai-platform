from app.parsers.txt_parser import TxtParser


def test_txt_parser_extracts_headings_and_paragraphs(sample_txt_path):
    doc = TxtParser().parse(sample_txt_path)
    assert doc.metadata.file_type.value == "txt"
    assert doc.sections, "Expected at least one top-level section"

    headings = [s.heading for s in doc.all_sections_flat() if s.heading]
    assert any("Introduction" in h for h in headings)
    assert any("Types of Force" in h for h in headings)


def test_txt_parser_extracts_list_items(sample_txt_path):
    doc = TxtParser().parse(sample_txt_path)
    all_blocks = [b for s in doc.all_sections_flat() for b in s.blocks]
    list_items = [b.text for b in all_blocks if b.type.value == "list_item"]
    assert "Muscular force" in list_items
    assert "Frictional force" in list_items


def test_txt_parser_extracts_urls(sample_txt_path):
    doc = TxtParser().parse(sample_txt_path)
    urls = [u.url for s in doc.all_sections_flat() for u in s.urls]
    assert any("ncert.nic.in" in u for u in urls)


def test_txt_parser_hierarchy_nesting(sample_txt_path):
    doc = TxtParser().parse(sample_txt_path)
    top_headings = [s.heading for s in doc.sections if s.heading]
    # "1.1 Types of Force" must not appear as a top-level/sibling heading -
    # it should only show up nested under "1. Introduction" (checked below).
    assert not any("Types of Force" in h for h in top_headings)
    # "1.1 Types of Force" should nest under "1. Introduction", not be a sibling.
    intro = next(s for s in doc.all_sections_flat() if s.heading and "Introduction" in s.heading)
    sub_headings = [s.heading for s in intro.subsections]
    assert any("Types of Force" in h for h in sub_headings)


def test_txt_parser_raises_on_missing_file(tmp_path):
    from app.core.exceptions import ParsingError
    import pytest

    with pytest.raises(ParsingError):
        TxtParser().parse(tmp_path / "does_not_exist.txt")
