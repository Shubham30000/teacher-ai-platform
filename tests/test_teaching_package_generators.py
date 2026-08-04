import pytest

from app.classification.models import ContentCategory, DifficultyLevel, DocumentMetadata
from app.core.exceptions import LLMGenerationError, TeachingPackageGenerationError
from app.knowledge_extraction.models import Concept, KnowledgeJSON, LearningObjective
from app.teaching_package.generators import (
    AssessmentGenerator,
    EntryTicketGenerator,
    LessonPlanGenerator,
    TeacherGuidanceGenerator,
)


class _FakeLLM:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.last_prompt = None

    def generate_json(self, prompt):
        self.last_prompt = prompt
        if self._error:
            raise self._error
        return self._response


def _sample_knowledge() -> KnowledgeJSON:
    return KnowledgeJSON(
        document_id="doc-1",
        learning_objectives=[LearningObjective(id="obj-1", text="Define force.")],
        concepts=[Concept(id="concept-1", name="Force", description="A push or pull.")],
    )


def _sample_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        document_id="doc-1",
        subject="Physics",
        grade=8,
        topic="Force and Pressure",
        chapter="Chapter 8",
        language="English",
        difficulty=DifficultyLevel.BEGINNER,
        category=ContentCategory.CONCEPTUAL,
        confidence=0.9,
    )


def test_lesson_plan_generator_parses_valid_response():
    response = {
        "total_periods": 1,
        "pacing_rationale": "Single short concept.",
        "periods": [
            {
                "period_number": 1,
                "duration_minutes": 40,
                "title": "Introducing Force",
                "learning_objectives": ["Define force."],
                "concepts_covered": ["Force"],
                "summary": "Introduce the concept of force.",
            }
        ],
    }
    generator = LessonPlanGenerator(llm_provider=_FakeLLM(response=response))
    plan = generator.generate(_sample_knowledge(), _sample_metadata())

    assert plan.total_periods == 1
    assert plan.periods[0].title == "Introducing Force"


def test_entry_ticket_generator_parses_valid_response():
    response = {"items": [{"period_number": 1, "question": "What is a push?", "expected_answer": "A force."}]}
    generator = EntryTicketGenerator(llm_provider=_FakeLLM(response=response))
    ticket = generator.generate(_sample_knowledge(), _sample_metadata())

    assert len(ticket.items) == 1
    assert ticket.items[0].period_number == 1


def test_assessment_generator_parses_valid_response():
    response = {
        "mcqs": [
            {
                "question": "What is force?",
                "options": ["A push or pull", "A color", "A sound"],
                "correct_option": "A push or pull",
                "explanation": "Force is defined as a push or pull.",
            }
        ],
        "short_answer": [],
        "long_answer": [],
        "numerical": [],
        "rubric": "1 mark per correct MCQ.",
    }
    generator = AssessmentGenerator(llm_provider=_FakeLLM(response=response))
    assessment = generator.generate(_sample_knowledge(), _sample_metadata())

    assert len(assessment.mcqs) == 1
    assert assessment.mcqs[0].correct_option == "A push or pull"


def test_teacher_guidance_generator_parses_valid_response():
    response = {
        "misconception_guidance": [
            {"misconception": "Force is a substance.", "remedial_action": "Clarify via examples.", "severity": "medium"}
        ],
        "teaching_tips": ["Use everyday push/pull examples."],
        "pacing_notes": "One period is sufficient for this scope.",
    }
    generator = TeacherGuidanceGenerator(llm_provider=_FakeLLM(response=response))
    guidance = generator.generate(_sample_knowledge(), _sample_metadata())

    assert guidance.misconception_guidance[0].severity == "medium"
    assert guidance.teaching_tips == ["Use everyday push/pull examples."]


def test_generator_wraps_llm_generation_error():
    generator = LessonPlanGenerator(llm_provider=_FakeLLM(error=LLMGenerationError("boom")))
    with pytest.raises(TeachingPackageGenerationError):
        generator.generate(_sample_knowledge(), _sample_metadata())


def test_generator_wraps_malformed_response():
    # "periods" must be a list of objects, not a string.
    response = {"total_periods": 1, "periods": "not-a-list"}
    generator = LessonPlanGenerator(llm_provider=_FakeLLM(response=response))
    with pytest.raises(TeachingPackageGenerationError):
        generator.generate(_sample_knowledge(), _sample_metadata())
