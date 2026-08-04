"""
Teaching Package orchestrator (Phase 2A).

Runs all nine generators against the same ``KnowledgeJSON`` +
``DocumentMetadata`` pair and collects their outputs into one
:class:`TeachingPackage`. Each generator's failure is isolated - one
module raising does not stop the others from running - matching the
Phase 2A objective's "handle failures independently" requirement.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.classification.models import DocumentMetadata
from app.core.exceptions import TeachingPackageGenerationError
from app.knowledge_extraction.models import KnowledgeJSON
from app.llm.gemini_client import TextGenerationProvider
from app.teaching_package.generators import (
    AssessmentGenerator,
    BlackboardNotesGenerator,
    ClassroomActivityGenerator,
    EntryTicketGenerator,
    ExitTicketGenerator,
    HomeworkGenerator,
    LessonPlanGenerator,
    TeacherGuidanceGenerator,
    TeacherScriptGenerator,
)
from app.teaching_package.models import TeachingPackage

logger = logging.getLogger(__name__)


class TeachingPackageOrchestrator:
    """Runs every Teaching Package generator and assembles the result."""

    def __init__(self, llm_provider: Optional[TextGenerationProvider] = None) -> None:
        self._generators = {
            "lesson_plan": LessonPlanGenerator(llm_provider),
            "entry_ticket": EntryTicketGenerator(llm_provider),
            "teacher_script": TeacherScriptGenerator(llm_provider),
            "blackboard_notes": BlackboardNotesGenerator(llm_provider),
            "classroom_activity": ClassroomActivityGenerator(llm_provider),
            "assessment": AssessmentGenerator(llm_provider),
            "exit_ticket": ExitTicketGenerator(llm_provider),
            "homework": HomeworkGenerator(llm_provider),
            "teacher_guidance": TeacherGuidanceGenerator(llm_provider),
        }

    def generate(self, knowledge: KnowledgeJSON, metadata: DocumentMetadata) -> TeachingPackage:
        results: dict = {}
        errors: dict[str, str] = {}

        # Improvement 1 (global period consistency): the Lesson Plan is the
        # single source of truth for how many periods this chapter needs, so
        # it must run first. Its total_periods is then handed to every other
        # generator so they all use the same count and numbering instead of
        # each independently guessing. If the Lesson Plan itself fails, the
        # other eight modules still run - they just fall back to deciding
        # their own period count, exactly as before.
        lesson_plan_generator = self._generators["lesson_plan"]
        total_periods: Optional[int] = None
        try:
            results["lesson_plan"] = lesson_plan_generator.generate(knowledge, metadata)
            total_periods = results["lesson_plan"].total_periods
        except TeachingPackageGenerationError as exc:
            logger.warning(
                "Teaching Package module '%s' failed for document %s: %s",
                "lesson_plan", knowledge.document_id, exc.message,
            )
            errors["lesson_plan"] = exc.message
            results["lesson_plan"] = None

        for name, generator in self._generators.items():
            if name == "lesson_plan":
                continue
            try:
                results[name] = generator.generate(knowledge, metadata, total_periods=total_periods)
            except TeachingPackageGenerationError as exc:
                logger.warning(
                    "Teaching Package module '%s' failed for document %s: %s",
                    name, knowledge.document_id, exc.message,
                )
                errors[name] = exc.message
                results[name] = None

        return TeachingPackage(
            document_id=knowledge.document_id,
            generation_errors=errors,
            **results,
        )
