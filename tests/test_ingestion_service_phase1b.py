from pathlib import Path

import pytest

from app.classification.models import ContentCategory, DifficultyLevel
from app.classification.models import DocumentMetadata as ClassificationMetadata
from app.core.constants import JobStage
from app.ingestion_service import run_ingestion
from app.knowledge_extraction.models import Concept, KnowledgeJSON, LearningObjective
from app.progress.tracker import ProgressTracker


class _StubEmbeddingProvider:
    def embed_documents(self, texts):
        return [[0.0] * 8 for _ in texts]

    def embed_query(self, text):
        return [0.0] * 8


class _StubVectorStore:
    def add_chunks(self, chunks, embeddings):
        return None


class _StubRetriever:
    def retrieve(self, query, top_k=5, document_id=None):
        return []


class _StubClassifier:
    def __init__(self):
        self.received_document = None

    def classify(self, document):
        self.received_document = document
        return ClassificationMetadata(
            document_id=document.document_id,
            subject="Physics",
            grade=8,
            topic="Force and Pressure",
            chapter="Chapter 8",
            language="English",
            difficulty=DifficultyLevel.BEGINNER,
            category=ContentCategory.CONCEPTUAL,
            confidence=0.9,
        )


class _StubKnowledgeExtractor:
    def __init__(self):
        self.received_metadata = None

    def extract(self, document, metadata):
        self.received_metadata = metadata
        return KnowledgeJSON(
            document_id=document.document_id,
            learning_objectives=[LearningObjective(id="obj-1", text="Define force.")],
            concepts=[Concept(id="concept-1", name="Force", description="A push or pull.")],
        )


@pytest.fixture
def tracker():
    return ProgressTracker()


def test_run_ingestion_populates_classification_and_knowledge_json(tracker, sample_txt_path: Path):
    job = tracker.create_job()
    classifier = _StubClassifier()
    extractor = _StubKnowledgeExtractor()

    outcome = run_ingestion(
        job.job_id,
        tracker,
        file_path=sample_txt_path,
        embedding_provider=_StubEmbeddingProvider(),
        vector_store=_StubVectorStore(),
        retriever=_StubRetriever(),
        classifier=classifier,
        knowledge_extractor=extractor,
    )

    assert outcome.document_metadata.subject == "Physics"
    assert outcome.knowledge_json.concepts[0].name == "Force"
    assert classifier.received_document is not None
    assert extractor.received_metadata.subject == "Physics"

    final_job = tracker.get_job(job.job_id)
    assert final_job.stage == JobStage.COMPLETED
    assert final_job.result["document_metadata"]["subject"] == "Physics"
    assert final_job.result["knowledge_json_summary"]["concepts"] == 1


def test_run_ingestion_reports_classifying_and_extracting_stages(tracker, sample_txt_path: Path):
    """Verifies the two new Phase 1B stages are visited, by tracking every
    stage the ProgressTracker sees via a thin wrapper."""
    seen_stages = []
    real_update_stage = tracker.update_stage

    def _tracking_update_stage(job_id, stage, *args, **kwargs):
        seen_stages.append(stage)
        return real_update_stage(job_id, stage, *args, **kwargs)

    tracker.update_stage = _tracking_update_stage

    job = tracker.create_job()
    run_ingestion(
        job.job_id,
        tracker,
        file_path=sample_txt_path,
        embedding_provider=_StubEmbeddingProvider(),
        vector_store=_StubVectorStore(),
        retriever=_StubRetriever(),
        classifier=_StubClassifier(),
        knowledge_extractor=_StubKnowledgeExtractor(),
    )

    assert JobStage.CLASSIFYING in seen_stages
    assert JobStage.EXTRACTING_KNOWLEDGE in seen_stages
    assert seen_stages.index(JobStage.CLASSIFYING) < seen_stages.index(JobStage.EXTRACTING_KNOWLEDGE)
    assert seen_stages.index(JobStage.EXTRACTING_KNOWLEDGE) < seen_stages.index(JobStage.COMPLETED)
