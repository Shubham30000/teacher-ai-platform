"""
Knowledge Extraction (Phase 1B).

Input: ``StructuredDocument`` + ``Retriever`` (Phase 1A's retrieval
layer, used to fetch the most relevant grounding context instead of
always processing the entire document, per PROJECT_ROADMAP.md item 13).

Output: :class:`app.knowledge_extraction.models.KnowledgeJSON`.

Grounding: the extraction prompt is explicitly instructed never to
introduce facts/concepts absent from the retrieved primary-source
context (mirrors FAQ Q4's definition of "hallucination" for this
project). Retrieved chunk ids are recorded on the resulting
``KnowledgeJSON.grounding_chunk_ids`` for traceability.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.classification.models import DocumentMetadata
from app.config import get_settings
from app.core.exceptions import KnowledgeExtractionError, LLMGenerationError, RetrievalError
from app.document_intelligence.models import StructuredDocument
from app.knowledge_extraction.models import KnowledgeJSON
from app.llm.gemini_client import GeminiTextGenerationProvider, TextGenerationProvider
from app.prompt_engine.loader import render_prompt
from app.retriever.retriever import Retriever
from pydantic import ValidationError

logger = logging.getLogger(__name__)

_PROMPT_NAME = "knowledge_extraction_prompt.md"


class KnowledgeExtractor:
    """Extracts a structured KnowledgeJSON from a StructuredDocument."""

    def __init__(
        self,
        llm_provider: Optional[TextGenerationProvider] = None,
        retriever: Optional[Retriever] = None,
    ) -> None:
        self._llm = llm_provider or GeminiTextGenerationProvider()
        self._retriever = retriever

    def extract(
        self,
        document: StructuredDocument,
        metadata: DocumentMetadata,
    ) -> KnowledgeJSON:
        settings = get_settings()
        context, grounding_chunk_ids = self._build_context(
            document, metadata, settings.knowledge_extraction_context_char_limit
        )

        prompt = render_prompt(
            _PROMPT_NAME,
            {
                "SUBJECT": metadata.subject or "unknown",
                "GRADE": str(metadata.grade) if metadata.grade is not None else "unknown",
                "TOPIC": metadata.topic or "unknown",
                "CHAPTER": metadata.chapter or "unknown",
                "DIFFICULTY": metadata.difficulty.value if metadata.difficulty else "unknown",
                "DOCUMENT_CONTEXT": context or "(no extractable text)",
            },
        )

        try:
            raw = self._llm.generate_json(prompt)
        except LLMGenerationError as exc:
            raise KnowledgeExtractionError(
                f"Knowledge Extraction failed for document {document.document_id}: {exc.message}"
            ) from exc

        return self._to_knowledge_json(document.document_id, raw, grounding_chunk_ids)

    # -- context assembly ----------------------------------------------

    def _build_context(
        self,
        document: StructuredDocument,
        metadata: DocumentMetadata,
        char_limit: int,
    ) -> tuple[str, List[str]]:
        """Prefer retrieval-selected chunks (grounded + traceable); fall back
        to a truncated full-text dump when retrieval is unavailable."""
        if self._retriever is not None:
            try:
                query = " ".join(
                    part for part in [metadata.topic, metadata.chapter, metadata.subject] if part
                ) or document.full_text()[:200]
                settings = get_settings()
                chunks = self._retriever.retrieve(
                    query,
                    top_k=settings.knowledge_extraction_retrieval_top_k,
                    document_id=document.document_id,
                )
                if chunks:
                    combined = "\n\n".join(
                        f"[{c.heading_path or 'section'}] {c.text}" for c in chunks
                    )
                    return combined[:char_limit], [c.chunk_id for c in chunks]
            except RetrievalError as exc:
                logger.warning(
                    "Retrieval unavailable for knowledge extraction of %s (%s); "
                    "falling back to full text.",
                    document.document_id, exc.message,
                )

        return document.full_text()[:char_limit], []

    # -- response parsing -------------------------------------------------

    def _to_knowledge_json(
        self, document_id: str, raw: dict, grounding_chunk_ids: List[str]
    ) -> KnowledgeJSON:
        try:
            return KnowledgeJSON(
                document_id=document_id,
                learning_objectives=raw.get("learning_objectives", []) or [],
                prerequisites=raw.get("prerequisites", []) or [],
                concepts=raw.get("concepts", []) or [],
                definitions=raw.get("definitions", []) or [],
                formulae=raw.get("formulae", []) or [],
                keywords=[str(k) for k in (raw.get("keywords", []) or [])],
                examples=raw.get("examples", []) or [],
                applications=raw.get("applications", []) or [],
                misconceptions=raw.get("misconceptions", []) or [],
                relationships=raw.get("relationships", []) or [],
                grounding_chunk_ids=grounding_chunk_ids,
            )
        except (ValueError, TypeError, ValidationError) as exc:
            raise KnowledgeExtractionError(
                f"Knowledge Extraction returned a malformed response for "
                f"document {document_id}: {exc}"
            ) from exc
