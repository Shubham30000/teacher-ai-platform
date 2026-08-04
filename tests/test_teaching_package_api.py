import io

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed in this environment")

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


def _stub_ingestion(monkeypatch):
    """Stubs everything Phase 1 needs so /upload runs end-to-end without
    external services, mirroring tests/test_api.py's existing convention."""
    from app import ingestion_service
    from app.classification.models import ContentCategory, DifficultyLevel, DocumentMetadata
    from app.knowledge_extraction.models import Concept, KnowledgeJSON, LearningObjective

    class _StubEmbeddingProvider:
        def embed_documents(self, texts):
            return [[0.0] * 8 for _ in texts]

        def embed_query(self, text):
            return [0.0] * 8

    class _StubVectorStore:
        def add_chunks(self, chunks, embeddings):
            return None

    class _StubRetriever:
        def __init__(self, *args, **kwargs):
            pass

        def retrieve(self, query, top_k=5, document_id=None):
            return []

    class _StubClassifier:
        def __init__(self, *args, **kwargs):
            pass

        def classify(self, document):
            return DocumentMetadata(
                document_id=document.document_id,
                subject="Physics",
                grade=8,
                topic="Force and Pressure",
                chapter="Force and Pressure",
                language="English",
                difficulty=DifficultyLevel.BEGINNER,
                category=ContentCategory.CONCEPTUAL,
                confidence=0.9,
            )

    class _StubKnowledgeExtractor:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, document, metadata):
            return KnowledgeJSON(
                document_id=document.document_id,
                learning_objectives=[LearningObjective(id="obj-1", text="Define force.")],
                concepts=[Concept(id="concept-1", name="Force", description="A push or pull.")],
            )

    monkeypatch.setattr(ingestion_service, "GeminiEmbeddingProvider", lambda: _StubEmbeddingProvider())
    monkeypatch.setattr(ingestion_service, "ChromaVectorStore", lambda: _StubVectorStore())
    monkeypatch.setattr(ingestion_service, "Retriever", _StubRetriever)
    monkeypatch.setattr(ingestion_service, "EducationalClassifier", _StubClassifier)
    monkeypatch.setattr(ingestion_service, "KnowledgeExtractor", _StubKnowledgeExtractor)


_ITEMS_RESPONSE = {"items": [{"period_number": 1, "question": "What is force?", "expected_answer": "A push or pull."}]}
_LESSON_PLAN_RESPONSE = {
    "total_periods": 1,
    "pacing_rationale": "Single concept.",
    "periods": [
        {
            "period_number": 1, "duration_minutes": 40, "title": "Force",
            "learning_objectives": ["Define force."], "concepts_covered": ["Force"],
            "summary": "Intro to force.",
        }
    ],
}
_ASSESSMENT_RESPONSE = {
    "mcqs": [{"question": "What is force?", "options": ["A push or pull", "A color"],
              "correct_option": "A push or pull", "explanation": "Definition."}],
    "short_answer": [], "long_answer": [], "numerical": [], "rubric": "1 mark per MCQ.",
}
_GUIDANCE_RESPONSE = {"misconception_guidance": [], "teaching_tips": ["Use examples."], "pacing_notes": "Fine as-is."}
_CLASSROOM_ACTIVITY_RESPONSE = {
    "items": [
        {
            "period_number": 1, "title": "Push or Pull Demo", "activity_type": "demonstration",
            "duration_minutes": 15, "materials_needed": ["a small box"],
            "instructions": "Push and pull the box.", "success_criteria": "Students name the force direction.",
        }
    ]
}


class _StubTeachingLLM:
    """Fake TextGenerationProvider that routes by prompt content, used for
    every one of the nine Teaching Package generators."""

    def generate_json(self, prompt):
        if "Lesson Planner" in prompt:
            return _LESSON_PLAN_RESPONSE
        if "Assessment" in prompt:
            return _ASSESSMENT_RESPONSE
        if "Teacher Guidance" in prompt:
            return _GUIDANCE_RESPONSE
        if "Classroom Activity" in prompt:
            return _CLASSROOM_ACTIVITY_RESPONSE
        return _ITEMS_RESPONSE


class _StubOrchestrator:
    """Wraps the real TeachingPackageOrchestrator with a stub LLM provider,
    so /upload exercises the real generator/parsing/orchestration logic
    without calling out to Gemini."""

    def __init__(self):
        from app.teaching_package.orchestrator import TeachingPackageOrchestrator
        self._inner = TeachingPackageOrchestrator(llm_provider=_StubTeachingLLM())

    def generate(self, knowledge, metadata):
        return self._inner.generate(knowledge, metadata)


def _stub_teaching_package_llm(monkeypatch):
    from app.api.routes import upload as upload_route

    monkeypatch.setattr(upload_route, "TeachingPackageOrchestrator", lambda: _StubOrchestrator())


def _upload_sample_document(client):
    content = b"Force and Pressure\n\n1. Introduction\n\nForce is a push or pull."
    files = {"file": ("chapter.txt", io.BytesIO(content), "text/plain")}
    return client.post("/api/v1/upload", files=files)


def test_upload_includes_teaching_package_summary(client, monkeypatch):
    _stub_ingestion(monkeypatch)
    _stub_teaching_package_llm(monkeypatch)

    response = _upload_sample_document(client)

    assert response.status_code == 200
    body = response.json()
    assert body["teaching_package_summary"] is not None
    assert "lesson_plan" in body["teaching_package_summary"]["modules_generated"]
    assert body["teaching_package_summary"]["modules_failed"] == []
    assert body["teaching_package_summary"]["total_periods"] == 1


def test_get_teaching_package_returns_stored_package(client, monkeypatch):
    _stub_ingestion(monkeypatch)
    _stub_teaching_package_llm(monkeypatch)

    upload_response = _upload_sample_document(client)
    document_id = upload_response.json()["document_id"]

    response = client.get(f"/api/v1/teaching-package/{document_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document_id
    assert body["lesson_plan"]["total_periods"] == 1
    assert len(body["assessment"]["mcqs"]) == 1


def test_get_teaching_package_returns_404_for_unknown_document(client):
    response = client.get("/api/v1/teaching-package/does-not-exist")
    assert response.status_code == 404
