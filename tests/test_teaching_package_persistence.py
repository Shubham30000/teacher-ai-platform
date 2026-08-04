from app.classification.models import ContentCategory, DifficultyLevel, DocumentMetadata
from app.core.exceptions import TeachingPackageNotFoundError
from app.knowledge_extraction.models import Concept, KnowledgeJSON, LearningObjective
from app.teaching_package.models import LessonPeriod, LessonPlan, TeachingPackage
from app.teaching_package.persistence import load_teaching_package, save_teaching_package

import pytest


def _sample_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        document_id="doc-persist-1",
        subject="Physics",
        grade=8,
        topic="Force and Pressure",
        chapter="Chapter 8",
        language="English",
        difficulty=DifficultyLevel.BEGINNER,
        category=ContentCategory.CONCEPTUAL,
        confidence=0.9,
    )


def _sample_knowledge() -> KnowledgeJSON:
    return KnowledgeJSON(
        document_id="doc-persist-1",
        learning_objectives=[LearningObjective(id="obj-1", text="Define force.")],
        concepts=[Concept(id="concept-1", name="Force", description="A push or pull.")],
    )


def _sample_package() -> TeachingPackage:
    return TeachingPackage(
        document_id="doc-persist-1",
        lesson_plan=LessonPlan(
            total_periods=1,
            pacing_rationale="Single concept.",
            periods=[
                LessonPeriod(
                    period_number=1, duration_minutes=40, title="Force",
                    learning_objectives=["Define force."], concepts_covered=["Force"],
                    summary="Intro.",
                )
            ],
        ),
        generation_errors={"assessment": "boom"},
    )


def test_save_and_load_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path / "outputs"))
    from app.config import get_settings
    get_settings.cache_clear()

    metadata = _sample_metadata()
    knowledge = _sample_knowledge()
    package = _sample_package()

    path = save_teaching_package(metadata, knowledge, package)
    assert path.is_file()

    loaded = load_teaching_package("doc-persist-1")
    assert loaded.document_id == "doc-persist-1"
    assert loaded.lesson_plan.total_periods == 1
    assert loaded.lesson_plan.periods[0].title == "Force"
    assert loaded.generation_errors == {"assessment": "boom"}
    assert loaded.assessment is None

    get_settings.cache_clear()


def test_load_missing_document_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path / "outputs"))
    from app.config import get_settings
    get_settings.cache_clear()

    with pytest.raises(TeachingPackageNotFoundError):
        load_teaching_package("does-not-exist")

    get_settings.cache_clear()
