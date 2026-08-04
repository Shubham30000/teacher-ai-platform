import io

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed in this environment")

fastapi_testclient = pytest.importorskip("starlette.testclient")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    from app.main import app

    return fastapi_testclient.TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200


def test_upload_rejects_unsupported_extension(client):
    files = {"file": ("notes.xyz", io.BytesIO(b"hello"), "application/octet-stream")}
    response = client.post("/api/v1/upload", files=files)
    assert response.status_code == 422


def _stub_ingestion_pipeline(monkeypatch):
    """
    Stubs the embedding provider, vector store, retriever, classifier, and
    knowledge extractor (all of which require external services/network) so
    a test exercises genuine parsing + chunking logic end-to-end via the
    API, without needing real network calls.
    """
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

    monkeypatch.setattr(
        ingestion_service, "GeminiEmbeddingProvider", lambda: _StubEmbeddingProvider()
    )
    monkeypatch.setattr(ingestion_service, "ChromaVectorStore", lambda: _StubVectorStore())
    monkeypatch.setattr(ingestion_service, "Retriever", _StubRetriever)
    monkeypatch.setattr(ingestion_service, "EducationalClassifier", _StubClassifier)
    monkeypatch.setattr(ingestion_service, "KnowledgeExtractor", _StubKnowledgeExtractor)


def test_upload_txt_end_to_end_through_parsing_and_chunking(client, monkeypatch):
    """POST /api/v1/upload is the Phase 2A contract: it blocks until the
    whole pipeline finishes and returns the complete result directly."""
    _stub_ingestion_pipeline(monkeypatch)

    content = b"Force and Pressure\n\n1. Introduction\n\nForce is a push or pull."
    files = {"file": ("chapter.txt", io.BytesIO(content), "text/plain")}
    response = client.post("/api/v1/upload", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"]
    assert body["chunk_count"] >= 1
    assert body["stage"] == "completed"
    assert body["document_metadata"]["subject"] == "Physics"
    assert body["knowledge_summary"]["concepts"] == 1


def test_upload_web_endpoint_runs_in_background_and_reports_via_progress(client, monkeypatch):
    """/api/v1/upload/web is the frontend-only path: it returns immediately
    with a queued job, and the same result ends up on the job's progress
    record once the (Starlette-test-client-synchronous) background task
    finishes."""
    _stub_ingestion_pipeline(monkeypatch)

    content = b"Force and Pressure\n\n1. Introduction\n\nForce is a push or pull."
    files = {"file": ("chapter.txt", io.BytesIO(content), "text/plain")}
    response = client.post("/api/v1/upload/web", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"]
    assert body["stage"] == "queued"

    progress_response = client.get(f"/api/v1/progress/{body['job_id']}")
    assert progress_response.status_code == 200
    job = progress_response.json()
    assert job["stage"] == "completed"
    result = job["result"]
    assert result["document_id"]
    assert result["chunk_count"] >= 1
    assert result["document_metadata"]["subject"] == "Physics"
    assert result["knowledge_summary"]["concepts"] == 1


def test_progress_endpoint_returns_404_for_unknown_job(client):
    response = client.get("/api/v1/progress/does-not-exist")
    assert response.status_code == 404
