from app.parsers.pptx_parser import PptxParser


def test_pptx_parser_creates_one_section_per_slide(sample_pptx_path):
    doc = PptxParser().parse(sample_pptx_path)
    assert len(doc.sections) == 2
    assert doc.sections[0].heading == "Force and Pressure"
    assert doc.sections[1].heading == "Types of Force"


def test_pptx_parser_extracts_body_text(sample_pptx_path):
    doc = PptxParser().parse(sample_pptx_path)
    slide1_texts = [b.text for b in doc.sections[0].blocks]
    assert "Push or pull is called force." in slide1_texts


def test_pptx_parser_metadata(sample_pptx_path):
    doc = PptxParser().parse(sample_pptx_path)
    assert doc.metadata.file_type.value == "pptx"
    assert doc.metadata.slide_count == 2
