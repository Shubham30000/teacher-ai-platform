import io

import pytest

from app.classification.models import ContentCategory, DifficultyLevel, DocumentMetadata
from app.knowledge_extraction.models import Concept, KnowledgeJSON, LearningObjective
from app.teaching_package.models import LessonPeriod, LessonPlan, TeachingPackage
from app.teaching_package.persistence import save_teaching_package
from app.utils.export_utils import build_teaching_package_sections, render_docx_bytes, render_pdf_bytes


def _sample_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        document_id="doc-export-1",
        subject="Physics",
        grade=8,
        topic="Force and Pressure",
        chapter="Chapter 8",
        language="English",
        difficulty=DifficultyLevel.BEGINNER,
        category=ContentCategory.CONCEPTUAL,
        confidence=0.9,
    )


def _sample_knowledge() -> KnowledgeJSON:
    return KnowledgeJSON(
        document_id="doc-export-1",
        learning_objectives=[LearningObjective(id="obj-1", text="Define force.")],
        concepts=[Concept(id="concept-1", name="Force", description="A push or pull.")],
    )


def _sample_package() -> TeachingPackage:
    return TeachingPackage(
        document_id="doc-export-1",
        lesson_plan=LessonPlan(
            total_periods=1,
            pacing_rationale="Single concept.",
            periods=[
                LessonPeriod(
                    period_number=1, duration_minutes=40, title="Force",
                    learning_objectives=["Define force."], concepts_covered=["Force"],
                    summary="Intro to force.",
                )
            ],
        ),
        generation_errors={"assessment": "boom"},
    )


def _sample_bundle() -> dict:
    return {
        "document_metadata": _sample_metadata().model_dump(mode="json"),
        "knowledge_json": _sample_knowledge().model_dump(mode="json"),
        "teaching_package": _sample_package().model_dump(mode="json"),
    }


def test_build_sections_includes_overview_and_lesson_plan():
    sections = build_teaching_package_sections(_sample_bundle())
    headings = [heading for heading, _ in sections]

    assert "Document Overview" in headings
    assert "Learning Objectives" in headings
    assert "Lesson Plan" in headings
    assert "Modules That Could Not Be Generated" in headings


def test_render_docx_bytes_produces_a_valid_docx():
    pytest.importorskip("docx")
    content = render_docx_bytes(_sample_bundle())
    assert content[:2] == b"PK"  # docx is a zip archive

    from docx import Document

    document = Document(io.BytesIO(content))
    assert len(document.paragraphs) > 0


def test_render_pdf_bytes_produces_a_valid_pdf():
    pytest.importorskip("fitz")
    content = render_pdf_bytes(_sample_bundle())
    assert content[:5] == b"%PDF-"


def test_render_docx_and_pdf_handle_missing_optional_modules():
    """A bundle with only a lesson plan (everything else None) must not
    raise - most sections in build_teaching_package_sections are optional."""
    pytest.importorskip("docx")
    pytest.importorskip("fitz")

    bundle = {
        "document_metadata": _sample_metadata().model_dump(mode="json"),
        "knowledge_json": {},
        "teaching_package": {"document_id": "doc-export-1"},
    }
    assert render_docx_bytes(bundle)[:2] == b"PK"
    assert render_pdf_bytes(bundle)[:5] == b"%PDF-"


fastapi = pytest.importorskip("fastapi", reason="fastapi not installed in this environment")
fastapi_testclient = pytest.importorskip("starlette.testclient")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path / "outputs"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    yield fastapi_testclient.TestClient(app)
    get_settings.cache_clear()


@pytest.fixture
def persisted_document(monkeypatch, tmp_path):
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path / "outputs"))
    from app.config import get_settings

    get_settings.cache_clear()
    save_teaching_package(_sample_metadata(), _sample_knowledge(), _sample_package())
    yield "doc-export-1"
    get_settings.cache_clear()


def test_export_json_returns_full_bundle(client, persisted_document):
    response = client.get(f"/api/v1/export/{persisted_document}/json")
    assert response.status_code == 200
    body = response.json()
    assert body["document_metadata"]["subject"] == "Physics"
    assert body["teaching_package"]["lesson_plan"]["total_periods"] == 1
    assert "attachment" in response.headers["content-disposition"]


def test_export_docx_returns_file(client, persisted_document):
    response = client.get(f"/api/v1/export/{persisted_document}/docx")
    assert response.status_code == 200
    assert response.content[:2] == b"PK"


def test_export_pdf_returns_file(client, persisted_document):
    response = client.get(f"/api/v1/export/{persisted_document}/pdf")
    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"


@pytest.mark.parametrize("fmt", ["json", "pdf", "docx"])
def test_export_returns_404_for_unknown_document(client, fmt):
    response = client.get(f"/api/v1/export/does-not-exist/{fmt}")
    assert response.status_code == 404
