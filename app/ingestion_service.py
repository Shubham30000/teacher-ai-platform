"""
Ingestion pipeline orchestration.

Wires together, in order: InputRouter -> EducationalChunker ->
GeminiEmbeddingProvider -> ChromaVectorStore, reporting progress at
each stage via ProgressTracker. This is what Phase 1A's end-of-phase
workflow diagram in PROJECT_ROADMAP.md describes:

    upload -> parse -> structure -> chunk -> embed -> ChromaDB -> retriever

Route handlers call :func:`run_ingestion`; nothing about FastAPI leaks
into this module, so it is directly unit-testable and directly reusable
by a future background-worker/queue implementation in Phase 1B.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.classification.classifier import EducationalClassifier
from app.classification.models import DocumentMetadata
from app.chunking.chunker import EducationalChunker
from app.core.constants import JobStage
from app.core.exceptions import TeacherPlatformError
from app.embeddings.gemini_embeddings import EmbeddingProvider, GeminiEmbeddingProvider
from app.input_router.router import InputRouter, RoutingRequest, RoutingResult
from app.knowledge_extraction.extractor import KnowledgeExtractor
from app.knowledge_extraction.models import KnowledgeJSON
from app.progress.tracker import ProgressTracker
from app.retriever.retriever import Retriever
from app.validation.validators import validate_document_metadata, validate_knowledge_json
from app.vectorstore.chroma_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class IngestionOutcome:
    def __init__(
        self,
        routing_result: RoutingResult,
        chunk_count: int = 0,
        document_metadata: Optional[DocumentMetadata] = None,
        knowledge_json: Optional[KnowledgeJSON] = None,
    ) -> None:
        self.routing_result = routing_result
        self.chunk_count = chunk_count
        self.document_metadata = document_metadata
        self.knowledge_json = knowledge_json


def run_ingestion(
    job_id: str,
    tracker: ProgressTracker,
    *,
    file_path: Optional[Path] = None,
    router: Optional[InputRouter] = None,
    chunker: Optional[EducationalChunker] = None,
    embedding_provider: Optional[EmbeddingProvider] = None,
    vector_store: Optional[ChromaVectorStore] = None,
    retriever: Optional[Retriever] = None,
    classifier: Optional[EducationalClassifier] = None,
    knowledge_extractor: Optional[KnowledgeExtractor] = None,
    mark_completed: bool = True,
) -> IngestionOutcome:
    router = router or InputRouter()
    chunker = chunker or EducationalChunker()
    embedding_provider = embedding_provider or GeminiEmbeddingProvider()
    vector_store = vector_store or ChromaVectorStore()

    try:
        tracker.update_stage(job_id, JobStage.ROUTING, "Routing request")
        routing_result = router.route(RoutingRequest(file_path=file_path))

        if routing_result.needs_clarification or routing_result.structured_document is None:
            tracker.update_stage(
                job_id,
                JobStage.COMPLETED,
                message=routing_result.clarification_message or "Clarification needed",
                result={"needs_clarification": True},
            )
            return IngestionOutcome(routing_result=routing_result, chunk_count=0)

        document = routing_result.structured_document

        tracker.update_stage(job_id, JobStage.STRUCTURING, "Document structured")

        tracker.update_stage(job_id, JobStage.CHUNKING, "Chunking document")
        chunks = chunker.chunk_document(document)

        tracker.update_stage(job_id, JobStage.EMBEDDING, f"Embedding {len(chunks)} chunks")
        texts = [chunk.text for chunk in chunks]
        embeddings = embedding_provider.embed_documents(texts) if texts else []

        tracker.update_stage(job_id, JobStage.INDEXING, "Writing to ChromaDB")
        vector_store.add_chunks(chunks, embeddings)

        # Retriever/classifier/extractor are only needed from here on, so they
        # are built lazily rather than unconditionally at the top of the
        # function (keeps the earlier upload-fallback / clarification path
        # free of any Gemini-generation dependency).
        active_retriever = retriever or Retriever(
            vector_store=vector_store, embedding_provider=embedding_provider
        )
        active_classifier = classifier or EducationalClassifier(retriever=active_retriever)
        active_extractor = knowledge_extractor or KnowledgeExtractor(retriever=active_retriever)

        tracker.update_stage(job_id, JobStage.CLASSIFYING, "Classifying document")
        document_metadata = active_classifier.classify(document)
        metadata_report = validate_document_metadata(document_metadata)
        if not metadata_report.is_valid:
            logger.warning(
                "Educational Classification for document %s has validation issues: %s",
                document.document_id,
                [issue.message for issue in metadata_report.issues if issue.severity == "error"],
            )

        tracker.update_stage(job_id, JobStage.EXTRACTING_KNOWLEDGE, "Extracting structured knowledge")
        knowledge_json = active_extractor.extract(document, document_metadata)
        knowledge_report = validate_knowledge_json(knowledge_json)
        if not knowledge_report.is_valid:
            logger.warning(
                "Knowledge Extraction for document %s has validation issues: %s",
                document.document_id,
                [issue.message for issue in knowledge_report.issues if issue.severity == "error"],
            )

        if mark_completed:
            tracker.update_stage(
                job_id,
                JobStage.COMPLETED,
                message="Ingestion complete",
                result={
                    "document_id": document.document_id,
                    "section_count": len(document.all_sections_flat()),
                    "chunk_count": len(chunks),
                    "document_metadata": document_metadata.model_dump(mode="json"),
                    "knowledge_json_summary": {
                        "learning_objectives": len(knowledge_json.learning_objectives),
                        "concepts": len(knowledge_json.concepts),
                        "definitions": len(knowledge_json.definitions),
                        "formulae": len(knowledge_json.formulae),
                        "examples": len(knowledge_json.examples),
                        "applications": len(knowledge_json.applications),
                        "misconceptions": len(knowledge_json.misconceptions),
                    },
                },
            )
        return IngestionOutcome(
            routing_result=routing_result,
            chunk_count=len(chunks),
            document_metadata=document_metadata,
            knowledge_json=knowledge_json,
        )

    except TeacherPlatformError as exc:
        logger.exception("Ingestion job %s failed", job_id)
        tracker.update_stage(job_id, JobStage.FAILED, error=exc.message)
        raise
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors via job status too
        logger.exception("Ingestion job %s failed unexpectedly", job_id)
        tracker.update_stage(job_id, JobStage.FAILED, error=str(exc))
        raise
