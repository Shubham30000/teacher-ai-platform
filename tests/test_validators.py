from app.chunking.chunker import EducationalChunker
from app.classification.models import ContentCategory, DifficultyLevel
from app.classification.models import DocumentMetadata as ClassificationMetadata
from app.document_intelligence.models import (
    ContentBlock,
    DocumentMetadata,
    HeadingLevel,
    Section,
    StructuredDocument,
)
from app.knowledge_extraction.models import (
    Concept,
    ConceptRelationship,
    Definition,
    KnowledgeJSON,
    LearningObjective,
)
from app.teaching_package.models import (
    EntryTicket,
    EntryTicketItem,
    LessonPeriod,
    LessonPlan,
    TeachingPackage,
)
from app.validation.validators import (
    validate_chunks,
    validate_document_metadata,
    validate_knowledge_json,
    validate_metadata_extraction,
    validate_structured_document,
    validate_teaching_package,
)


def _valid_document() -> StructuredDocument:
    section = Section(heading="1. Introduction", heading_level=HeadingLevel.H1)
    section.blocks.append(ContentBlock(text="Force is a push or pull on an object."))
    return StructuredDocument(
        metadata=DocumentMetadata(source_filename="x.txt", file_type="txt", file_size_bytes=100),
        sections=[section],
    )


def test_validate_structured_document_passes_for_good_document():
    report = validate_structured_document(_valid_document())
    assert report.is_valid
    assert not any(i.severity == "error" for i in report.issues)


def test_validate_structured_document_flags_empty_sections():
    doc = StructuredDocument(metadata=DocumentMetadata(source_filename="x.txt"), sections=[])
    report = validate_structured_document(doc)
    assert not report.is_valid
    assert any("no sections" in i.message.lower() for i in report.issues)


def test_validate_structured_document_flags_missing_file_type():
    doc = _valid_document()
    doc.metadata.file_type = None
    report = validate_structured_document(doc)
    assert not report.is_valid


def test_validate_chunks_detects_empty_chunk_list():
    doc = _valid_document()
    report = validate_chunks(doc, [])
    assert not report.is_valid


def test_validate_chunks_passes_for_real_chunker_output():
    doc = _valid_document()
    chunks = EducationalChunker(max_tokens=200, overlap_tokens=10, min_tokens=1).chunk_document(doc)
    report = validate_chunks(doc, chunks)
    assert report.is_valid


def test_validate_metadata_extraction_flags_negative_size():
    doc = _valid_document()
    doc.metadata.file_size_bytes = -5
    report = validate_metadata_extraction(doc)
    assert not report.is_valid


# -- Phase 1B: Educational Classification (DocumentMetadata) validation -----


def _valid_classification_metadata() -> ClassificationMetadata:
    return ClassificationMetadata(
        document_id="doc-1",
        subject="Physics",
        grade=8,
        topic="Force and Pressure",
        chapter="Chapter 8",
        language="English",
        difficulty=DifficultyLevel.BEGINNER,
        category=ContentCategory.CONCEPTUAL,
        confidence=0.85,
    )


def test_validate_document_metadata_passes_for_complete_metadata():
    report = validate_document_metadata(_valid_classification_metadata())
    assert report.is_valid


def test_validate_document_metadata_flags_missing_subject():
    metadata = _valid_classification_metadata()
    metadata.subject = None
    report = validate_document_metadata(metadata)
    assert not report.is_valid
    assert any(i.field == "subject" for i in report.issues)


def test_validate_document_metadata_missing_grade_is_only_a_warning():
    metadata = _valid_classification_metadata()
    metadata.grade = None
    report = validate_document_metadata(metadata)
    assert report.is_valid
    assert any(i.field == "grade" and i.severity == "warning" for i in report.issues)


def test_validate_document_metadata_flags_low_confidence():
    metadata = _valid_classification_metadata()
    metadata.confidence = 0.1
    report = validate_document_metadata(metadata)
    assert any(i.field == "confidence" and i.severity == "warning" for i in report.issues)


# -- Phase 1B: Knowledge Extraction (KnowledgeJSON) validation --------------


def _valid_knowledge_json() -> KnowledgeJSON:
    return KnowledgeJSON(
        document_id="doc-1",
        learning_objectives=[LearningObjective(id="obj-1", text="Define force.")],
        concepts=[
            Concept(id="concept-1", name="Force", description="A push or pull."),
            Concept(id="concept-2", name="Pressure", description="Force per unit area.",
                    related_concept_ids=["concept-1"]),
        ],
        definitions=[Definition(id="def-1", term="Force", definition="A push or pull.",
                                 concept_id="concept-1")],
        relationships=[
            ConceptRelationship(
                source_concept_id="concept-1",
                target_concept_id="concept-2",
                relationship_type="related_to",
            )
        ],
    )


def test_validate_knowledge_json_passes_for_well_formed_document():
    report = validate_knowledge_json(_valid_knowledge_json())
    assert report.is_valid


def test_validate_knowledge_json_flags_missing_concepts():
    knowledge = _valid_knowledge_json()
    knowledge.concepts = []
    report = validate_knowledge_json(knowledge)
    assert not report.is_valid
    assert any(i.field == "concepts" for i in report.issues)


def test_validate_knowledge_json_flags_missing_learning_objectives():
    knowledge = _valid_knowledge_json()
    knowledge.learning_objectives = []
    report = validate_knowledge_json(knowledge)
    assert not report.is_valid


def test_validate_knowledge_json_flags_dangling_concept_reference():
    knowledge = _valid_knowledge_json()
    knowledge.definitions[0].concept_id = "concept-does-not-exist"
    report = validate_knowledge_json(knowledge)
    assert not report.is_valid
    assert any("unknown concept_id" in i.message for i in report.issues)


def test_validate_knowledge_json_flags_duplicate_ids():
    knowledge = _valid_knowledge_json()
    knowledge.concepts.append(Concept(id="concept-1", name="Duplicate", description=""))
    report = validate_knowledge_json(knowledge)
    assert not report.is_valid
    assert any("Duplicate id" in i.message for i in report.issues)


def test_validate_knowledge_json_missing_definitions_is_only_a_warning():
    knowledge = _valid_knowledge_json()
    knowledge.definitions = []
    report = validate_knowledge_json(knowledge)
    assert report.is_valid
    assert any(i.field == "definitions" and i.severity == "warning" for i in report.issues)


def _two_period_lesson_plan() -> LessonPlan:
    return LessonPlan(
        total_periods=2,
        pacing_rationale="Split across two periods.",
        periods=[
            LessonPeriod(period_number=1, duration_minutes=40, title="Force"),
            LessonPeriod(period_number=2, duration_minutes=40, title="Pressure"),
        ],
    )


def test_validate_teaching_package_flags_period_mismatch():
    package = TeachingPackage(
        document_id="doc-1",
        lesson_plan=_two_period_lesson_plan(),
        entry_ticket=EntryTicket(
            items=[EntryTicketItem(period_number=1, question="What is force?")]
        ),
    )
    report = validate_teaching_package(package)

    mismatch_issues = [i for i in report.issues if i.field == "entry_ticket"]
    assert len(mismatch_issues) == 1
    assert mismatch_issues[0].severity == "warning"
    assert "do not match" in mismatch_issues[0].message


def test_validate_teaching_package_passes_when_periods_match():
    package = TeachingPackage(
        document_id="doc-1",
        lesson_plan=_two_period_lesson_plan(),
        entry_ticket=EntryTicket(
            items=[
                EntryTicketItem(period_number=1, question="What is force?"),
                EntryTicketItem(period_number=2, question="What is pressure?"),
            ]
        ),
    )
    report = validate_teaching_package(package)

    assert not any(i.field == "entry_ticket" for i in report.issues)
