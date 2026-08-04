"""
Validation (PROJECT_ROADMAP.md item 12).

Pure, side-effect-free checks over the pipeline's own data structures.
These are used both by the integration test suite and are available to
call directly (e.g. from an admin/debug endpoint in a later phase) to
sanity-check a document that went through ingestion.

Each ``validate_*`` function returns a :class:`ValidationReport`
rather than raising, so callers can decide whether a given failure is
fatal.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.chunking.models import Chunk
from app.classification.models import DocumentMetadata
from app.document_intelligence.models import StructuredDocument
from app.knowledge_extraction.models import KnowledgeJSON
from app.teaching_package.models import MODULE_NAMES, TeachingPackage


class ValidationIssue(BaseModel):
    field: str
    message: str
    severity: str = "error"  # "error" | "warning"


class ValidationReport(BaseModel):
    is_valid: bool
    issues: List[ValidationIssue] = Field(default_factory=list)

    def add(self, field: str, message: str, severity: str = "error") -> None:
        self.issues.append(ValidationIssue(field=field, message=message, severity=severity))
        if severity == "error":
            self.is_valid = False


def validate_structured_document(document: StructuredDocument) -> ValidationReport:
    """Validate parser output: metadata, hierarchy, and non-empty content."""
    report = ValidationReport(is_valid=True)

    if document.metadata is None:
        report.add("metadata", "StructuredDocument is missing metadata")
    else:
        if not document.metadata.source_filename and not document.metadata.source_url:
            report.add(
                "metadata.source", "Neither source_filename nor source_url is set", "warning"
            )
        if document.metadata.file_type is None:
            report.add("metadata.file_type", "file_type is not set")

    if not document.sections:
        report.add("sections", "Document has no sections at all")
        return report

    if not document.full_text().strip():
        report.add("sections", "Document has sections but no extractable text")

    _validate_hierarchy(document, report)
    return report


def _validate_hierarchy(document: StructuredDocument, report: ValidationReport) -> None:
    """Confirm heading levels only increase by one level of nesting per hop."""
    for section in document.sections:
        _validate_section_hierarchy(section, report)


def _validate_section_hierarchy(section, report: ValidationReport) -> None:
    for sub in section.subsections:
        if section.heading is not None and sub.heading_level.value <= section.heading_level.value:
            report.add(
                "hierarchy",
                f"Subsection '{sub.heading}' (level {sub.heading_level.value}) is not deeper "
                f"than its parent '{section.heading}' (level {section.heading_level.value})",
                "warning",
            )
        _validate_section_hierarchy(sub, report)


def validate_chunks(document: StructuredDocument, chunks: List[Chunk]) -> ValidationReport:
    """Validate chunking output: coverage, ordering, and non-empty text."""
    report = ValidationReport(is_valid=True)

    if not chunks:
        report.add("chunks", "No chunks were produced from a non-empty document")
        return report

    seen_ids = set()
    for chunk in chunks:
        if chunk.chunk_id in seen_ids:
            report.add("chunk_id", f"Duplicate chunk_id detected: {chunk.chunk_id}")
        seen_ids.add(chunk.chunk_id)

        if not chunk.text.strip():
            report.add("chunk.text", f"Chunk {chunk.chunk_id} has empty text")
        if chunk.document_id != document.document_id:
            report.add(
                "chunk.document_id",
                f"Chunk {chunk.chunk_id} document_id does not match source document",
            )
        if chunk.approx_token_count <= 0:
            report.add("chunk.approx_token_count", f"Chunk {chunk.chunk_id} has non-positive token count")

    indices = [c.chunk_index for c in chunks]
    if indices != sorted(indices):
        report.add("chunk_index", "Chunk indices are not in non-decreasing order")

    return report


def validate_metadata_extraction(document: StructuredDocument) -> ValidationReport:
    """Focused metadata-only validation, useful right after parsing."""
    report = ValidationReport(is_valid=True)
    meta = document.metadata
    if meta.file_size_bytes is not None and meta.file_size_bytes <= 0:
        report.add("metadata.file_size_bytes", "file_size_bytes must be positive")
    if meta.file_type is None:
        report.add("metadata.file_type", "file_type was not detected")
    return report


def validate_document_metadata(metadata: DocumentMetadata) -> ValidationReport:
    """Validate Educational Classification output (Phase 1B).

    ``subject``, ``topic``, ``language``, ``difficulty``, and ``category``
    are treated as required - a classification missing any of these is
    not useful downstream. ``grade`` and ``chapter`` are legitimately
    absent for some content (e.g. teacher-uploaded reference material
    without an explicit grade/chapter), so their
    absence is only a warning.
    """
    report = ValidationReport(is_valid=True)

    if not metadata.subject:
        report.add("subject", "DocumentMetadata is missing subject")
    if not metadata.topic:
        report.add("topic", "DocumentMetadata is missing topic")
    if not metadata.language:
        report.add("language", "DocumentMetadata is missing language")
    if metadata.difficulty is None:
        report.add("difficulty", "DocumentMetadata is missing difficulty")
    if metadata.category is None:
        report.add("category", "DocumentMetadata is missing category")

    if metadata.grade is None:
        report.add("grade", "DocumentMetadata has no grade level", "warning")
    if not metadata.chapter:
        report.add("chapter", "DocumentMetadata has no chapter", "warning")

    if metadata.confidence < 0.4:
        report.add(
            "confidence",
            f"Classification confidence is low ({metadata.confidence:.2f})",
            "warning",
        )

    return report


def validate_knowledge_json(knowledge: KnowledgeJSON) -> ValidationReport:
    """Validate Knowledge Extraction output (Phase 1B).

    Checks structural completeness and internal reference consistency.
    Grounding itself (does each claim trace back to the source) is the
    caller's responsibility at extraction time, per FAQ Q4.
    """
    report = ValidationReport(is_valid=True)

    if not knowledge.learning_objectives:
        report.add("learning_objectives", "KnowledgeJSON has no learning objectives")
    if not knowledge.concepts:
        report.add("concepts", "KnowledgeJSON has no concepts")

    if not knowledge.definitions:
        report.add("definitions", "KnowledgeJSON has no definitions", "warning")
    if not knowledge.keywords:
        report.add("keywords", "KnowledgeJSON has no keywords", "warning")
    if not knowledge.examples:
        report.add("examples", "KnowledgeJSON has no examples", "warning")
    if not knowledge.misconceptions:
        report.add("misconceptions", "KnowledgeJSON has no misconceptions", "warning")

    concept_ids = {c.id for c in knowledge.concepts}
    _check_duplicate_ids(knowledge.learning_objectives, "learning_objectives", report)
    _check_duplicate_ids(knowledge.prerequisites, "prerequisites", report)
    _check_duplicate_ids(knowledge.concepts, "concepts", report)
    _check_duplicate_ids(knowledge.definitions, "definitions", report)
    _check_duplicate_ids(knowledge.formulae, "formulae", report)
    _check_duplicate_ids(knowledge.examples, "examples", report)
    _check_duplicate_ids(knowledge.applications, "applications", report)
    _check_duplicate_ids(knowledge.misconceptions, "misconceptions", report)

    for concept in knowledge.concepts:
        for related_id in concept.related_concept_ids:
            if related_id not in concept_ids:
                report.add(
                    "concepts.related_concept_ids",
                    f"Concept '{concept.id}' references unknown related_concept_id '{related_id}'",
                )

    for definition in knowledge.definitions:
        if definition.concept_id and definition.concept_id not in concept_ids:
            report.add(
                "definitions.concept_id",
                f"Definition '{definition.id}' references unknown concept_id '{definition.concept_id}'",
            )

    for example in knowledge.examples:
        if example.concept_id and example.concept_id not in concept_ids:
            report.add(
                "examples.concept_id",
                f"Example '{example.id}' references unknown concept_id '{example.concept_id}'",
            )

    for misconception in knowledge.misconceptions:
        if misconception.related_concept_id and misconception.related_concept_id not in concept_ids:
            report.add(
                "misconceptions.related_concept_id",
                f"Misconception '{misconception.id}' references unknown "
                f"related_concept_id '{misconception.related_concept_id}'",
            )

    for relationship in knowledge.relationships:
        if relationship.source_concept_id not in concept_ids:
            report.add(
                "relationships.source_concept_id",
                f"Relationship references unknown source_concept_id "
                f"'{relationship.source_concept_id}'",
            )
        if relationship.target_concept_id not in concept_ids:
            report.add(
                "relationships.target_concept_id",
                f"Relationship references unknown target_concept_id "
                f"'{relationship.target_concept_id}'",
            )

    return report


def validate_teaching_package(package: TeachingPackage) -> ValidationReport:
    """Validate Phase 2A output: required modules present, non-empty content.

    A module that failed generation (``None``, recorded in
    ``generation_errors``) is a warning, not an error - Phase 2A's
    orchestrator is expected to keep going even when a module fails,
    so this validation must not treat that as fatal.
    """
    report = ValidationReport(is_valid=True)

    for name in MODULE_NAMES:
        value = getattr(package, name)
        if value is None:
            reason = package.generation_errors.get(name, "not generated")
            report.add(name, f"Module '{name}' is missing ({reason})", "warning")

    if package.lesson_plan is not None and not package.lesson_plan.periods:
        report.add("lesson_plan.periods", "Lesson plan has no periods", "warning")

    _validate_period_consistency(package, report)

    if package.assessment is not None:
        assessment = package.assessment
        if not (
            assessment.mcqs or assessment.short_answer
            or assessment.long_answer or assessment.numerical
        ):
            report.add("assessment", "Assessment has no questions of any kind", "warning")

    for field_name in ("entry_ticket", "teacher_script", "blackboard_notes",
                       "classroom_activity", "exit_ticket", "homework"):
        value = getattr(package, field_name)
        if value is not None and not value.items:
            report.add(field_name, f"Module '{field_name}' produced no items", "warning")

    return report


_PERIOD_NUMBERED_MODULES = (
    "entry_ticket", "teacher_script", "blackboard_notes",
    "classroom_activity", "exit_ticket", "homework",
)


def _validate_period_consistency(package: TeachingPackage, report: ValidationReport) -> None:
    """Confirm every period-numbered module covers the same periods as the
    Lesson Plan (assignment Stage 9: "consistency across periods").

    A mismatch is a warning, not an error, for the same reason a missing
    module is only a warning: one module disagreeing with the Lesson Plan
    should not make the whole Teaching Package invalid, just flag it for
    review.
    """
    if package.lesson_plan is None or not package.lesson_plan.periods:
        return

    expected = {period.period_number for period in package.lesson_plan.periods}

    for field_name in _PERIOD_NUMBERED_MODULES:
        module = getattr(package, field_name)
        if module is None or not module.items:
            continue
        actual = {item.period_number for item in module.items}
        if actual != expected:
            report.add(
                field_name,
                f"Module '{field_name}' periods {sorted(actual)} do not match "
                f"Lesson Plan periods {sorted(expected)}",
                "warning",
            )


def _check_duplicate_ids(items: List, field: str, report: ValidationReport) -> None:
    seen = set()
    for item in items:
        if item.id in seen:
            report.add(field, f"Duplicate id detected in {field}: '{item.id}'")
        seen.add(item.id)
