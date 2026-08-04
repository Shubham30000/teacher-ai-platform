import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed in this environment")

from app.parsers.pdf_parser import PdfParser  # noqa: E402


@pytest.fixture
def sample_pdf_path(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Force and Pressure", fontsize=24)
    page.insert_text((72, 120), "1. Introduction", fontsize=16)
    page.insert_text(
        (72, 150),
        "Push or pull is called force. It changes speed, shape or direction.",
        fontsize=11,
    )
    path = tmp_path / "sample.pdf"
    doc.save(str(path))
    doc.close()
    return path


def test_pdf_parser_extracts_headings_by_font_size(sample_pdf_path):
    doc = PdfParser().parse(sample_pdf_path)
    headings = [s.heading for s in doc.all_sections_flat() if s.heading]
    assert any("Force and Pressure" in h for h in headings)
    assert any("Introduction" in h for h in headings)


def test_pdf_parser_metadata(sample_pdf_path):
    doc = PdfParser().parse(sample_pdf_path)
    assert doc.metadata.file_type.value == "pdf"
    assert doc.metadata.page_count == 1
