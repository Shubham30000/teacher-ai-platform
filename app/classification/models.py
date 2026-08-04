"""
Educational Classification data contract (Phase 1B, PROJECT_ROADMAP.md
section 14.1).

Note: this is deliberately a *different* ``DocumentMetadata`` from
``app.document_intelligence.models.DocumentMetadata``. That earlier
model captures file-level metadata (filename, file type, page count)
produced by parsing. This module's ``DocumentMetadata`` is the
pedagogical classification output (subject/grade/topic/...) produced
by the Educational Classifier from an already-parsed document. The two
live in separate modules and are never imported together under the
same name; callers that need both import one with an alias, e.g.::

    from app.document_intelligence.models import DocumentMetadata as FileMetadata
    from app.classification.models import DocumentMetadata
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ContentCategory(str, Enum):
    """The pedagogical nature of the content, independent of subject."""

    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"
    FACTUAL = "factual"
    ANALYTICAL = "analytical"
    APPLIED = "applied"


class DocumentMetadata(BaseModel):
    """Educational classification of a StructuredDocument.

    Produced by :class:`app.classification.classifier.EducationalClassifier`
    from a ``StructuredDocument`` (+ optional retrieved context). Consumed
    by Knowledge Extraction and every downstream Phase 2 stage for context,
    per PROJECT_ROADMAP.md section 14.1.
    """

    document_id: str
    subject: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    topic: Optional[str] = None
    chapter: Optional[str] = None
    language: Optional[str] = None
    difficulty: Optional[DifficultyLevel] = None
    category: Optional[ContentCategory] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("subject", "topic", "chapter", "language", mode="before")
    @classmethod
    def _blank_string_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value
