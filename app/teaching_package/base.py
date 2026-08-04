"""
Shared base class for the nine Phase 2A Teaching Package generators.

Every generator follows the same shape as
``app.classification.classifier.EducationalClassifier`` and
``app.knowledge_extraction.extractor.KnowledgeExtractor``: render a
Markdown prompt, call the Gemini JSON provider, parse the result into
a Pydantic model. The only thing that differs between the nine modules
is the prompt template and the parsing step, so those two things are
the only per-module overrides; everything else (input variables, error
handling) is shared here to avoid nine near-identical copies of the
same boilerplate.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Mapping, Optional

from pydantic import BaseModel, ValidationError

from app.classification.models import DocumentMetadata
from app.core.exceptions import LLMGenerationError, TeachingPackageGenerationError
from app.knowledge_extraction.models import KnowledgeJSON
from app.llm.gemini_client import GeminiTextGenerationProvider, TextGenerationProvider
from app.prompt_engine.loader import render_prompt

logger = logging.getLogger(__name__)


class BaseTeachingGenerator:
    """Base class for a single Teaching Package module generator.

    Subclasses set ``prompt_name`` and implement ``_parse`` to turn the
    raw JSON dict returned by the LLM into their specific output model.
    """

    prompt_name: str = ""

    def __init__(self, llm_provider: TextGenerationProvider | None = None) -> None:
        self._llm = llm_provider or GeminiTextGenerationProvider()

    def generate(
        self,
        knowledge: KnowledgeJSON,
        metadata: DocumentMetadata,
        total_periods: Optional[int] = None,
    ) -> BaseModel:
        if not self.prompt_name:
            raise NotImplementedError("Subclasses must set prompt_name")

        prompt = render_prompt(
            self.prompt_name, self._build_variables(knowledge, metadata, total_periods)
        )

        try:
            raw = self._llm.generate_json(prompt)
        except LLMGenerationError as exc:
            raise TeachingPackageGenerationError(
                f"{type(self).__name__} failed for document {knowledge.document_id}: {exc.message}"
            ) from exc

        try:
            return self._parse(raw)
        except (ValueError, TypeError, ValidationError) as exc:
            raise TeachingPackageGenerationError(
                f"{type(self).__name__} returned a malformed response for "
                f"document {knowledge.document_id}: {exc}"
            ) from exc

    # -- shared prompt context -------------------------------------------

    def _build_variables(
        self,
        knowledge: KnowledgeJSON,
        metadata: DocumentMetadata,
        total_periods: Optional[int] = None,
    ) -> Mapping[str, str]:
        return {
            "SUBJECT": metadata.subject or "unknown",
            "GRADE": str(metadata.grade) if metadata.grade is not None else "unknown",
            "TOPIC": metadata.topic or "unknown",
            "CHAPTER": metadata.chapter or "unknown",
            "DIFFICULTY": metadata.difficulty.value if metadata.difficulty else "unknown",
            "LANGUAGE": metadata.language or "English",
            "KNOWLEDGE_JSON": json.dumps(
                knowledge.model_dump(mode="json"), indent=2, ensure_ascii=False
            ),
            "TOTAL_PERIODS": self._format_total_periods(total_periods),
        }

    @staticmethod
    def _format_total_periods(total_periods: Optional[int]) -> str:
        """Render the Lesson Plan's period count for injection into every
        other module's prompt (Improvement 1: global period consistency).

        When the Lesson Plan has not been generated yet, or failed to
        generate, this falls back to instructing the model to decide a
        sensible number itself - the previous, per-module behaviour -
        so a Lesson Plan failure never blocks the other eight modules.
        """
        if total_periods and total_periods > 0:
            return (
                f"exactly {total_periods} (fixed by the Lesson Plan, which is the "
                "single source of truth for period count and numbering - generate "
                "content for all of these periods, do not add or omit any, and use "
                "identical period numbering)"
            )
        return (
            "not yet determined - decide a sensible number yourself based on the "
            "volume of content above"
        )

    # -- per-module parsing ------------------------------------------------

    def _parse(self, raw: dict[str, Any]) -> BaseModel:
        raise NotImplementedError
