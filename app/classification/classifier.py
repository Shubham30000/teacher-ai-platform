"""
Educational Classification (Phase 1B).

Input: ``StructuredDocument`` (+ optionally the ``Retriever`` built in
Phase 1A, so classification can work off a representative, retrieval-
selected subset of a long document instead of the entire text).

Output: :class:`app.classification.models.DocumentMetadata`.

Uses Gemini with structured JSON output (``GeminiTextGenerationProvider``)
against ``prompts/classification_prompt.md``. Never talks to the Gemini
SDK or the filesystem directly - both are delegated to
``app.llm.gemini_client`` and ``app.prompt_engine.loader`` respectively,
keeping this module focused on orchestration and validation only.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.classification.models import ContentCategory, DifficultyLevel, DocumentMetadata
from app.config import get_settings
from app.core.exceptions import ClassificationError, LLMGenerationError, RetrievalError
from app.document_intelligence.models import StructuredDocument
from app.llm.gemini_client import GeminiTextGenerationProvider, TextGenerationProvider
from app.prompt_engine.loader import render_prompt
from app.retriever.retriever import Retriever
from pydantic import ValidationError

logger = logging.getLogger(__name__)

_PROMPT_NAME = "classification_prompt.md"


class EducationalClassifier:
    """Classifies a StructuredDocument into pedagogical metadata."""

    def __init__(
        self,
        llm_provider: Optional[TextGenerationProvider] = None,
        retriever: Optional[Retriever] = None,
    ) -> None:
        self._llm = llm_provider or GeminiTextGenerationProvider()
        self._retriever = retriever  # may stay None; retrieval is opportunistic here

    def classify(self, document: StructuredDocument) -> DocumentMetadata:
        settings = get_settings()
        heading_outline = self._build_heading_outline(document)
        context = self._build_context(document, settings.classification_context_char_limit)

        prompt = render_prompt(
            _PROMPT_NAME,
            {
                "SOURCE_FILENAME": document.metadata.source_filename or "unknown",
                "HEADING_OUTLINE": heading_outline or "(no headings detected)",
                "DOCUMENT_CONTEXT": context or "(no extractable text)",
            },
        )

        try:
            raw = self._llm.generate_json(prompt)
        except LLMGenerationError as exc:
            raise ClassificationError(
                f"Educational Classification failed for document {document.document_id}: {exc.message}"
            ) from exc

        return self._to_metadata(document.document_id, raw)

    # -- context assembly ----------------------------------------------

    def _build_heading_outline(self, document: StructuredDocument) -> str:
        lines = []
        for section in document.all_sections_flat():
            if section.heading:
                indent = "  " * max(0, section.heading_level.value)
                lines.append(f"{indent}- {section.heading}")
        return "\n".join(lines)

    def _build_context(self, document: StructuredDocument, char_limit: int) -> str:
        """Prefer retrieval-selected representative chunks for long documents;
        fall back to a truncated full-text dump when no retriever is available
        or retrieval fails/returns nothing."""
        if self._retriever is not None:
            try:
                query = document.metadata.title or document.full_text()[:200] or "chapter overview"
                settings = get_settings()
                chunks = self._retriever.retrieve(
                    query,
                    top_k=settings.classification_retrieval_top_k,
                    document_id=document.document_id,
                )
                if chunks:
                    combined = "\n\n".join(
                        f"[{c.heading_path or 'section'}] {c.text}" for c in chunks
                    )
                    return combined[:char_limit]
            except RetrievalError as exc:
                logger.warning(
                    "Retrieval unavailable for classification of %s (%s); falling back to full text.",
                    document.document_id, exc.message,
                )

        return document.full_text()[:char_limit]

    # -- response parsing -------------------------------------------------

    def _to_metadata(self, document_id: str, raw: dict) -> DocumentMetadata:
        try:
            difficulty = raw.get("difficulty")
            category = raw.get("category")
            return DocumentMetadata(
                document_id=document_id,
                subject=raw.get("subject"),
                grade=raw.get("grade"),
                topic=raw.get("topic"),
                chapter=raw.get("chapter"),
                language=raw.get("language"),
                difficulty=DifficultyLevel(difficulty) if difficulty else None,
                category=ContentCategory(category) if category else None,
                confidence=float(raw.get("confidence", 0.0)),
            )
        except (ValueError, TypeError, ValidationError) as exc:
            raise ClassificationError(
                f"Educational Classification returned a malformed response for "
                f"document {document_id}: {exc}"
            ) from exc
