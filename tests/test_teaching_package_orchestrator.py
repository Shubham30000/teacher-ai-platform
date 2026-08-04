from app.classification.models import ContentCategory, DifficultyLevel, DocumentMetadata
from app.core.exceptions import LLMGenerationError
from app.knowledge_extraction.models import Concept, KnowledgeJSON, LearningObjective
from app.teaching_package.orchestrator import TeachingPackageOrchestrator


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


_LESSON_PLAN_RESPONSE = {
    "total_periods": 1,
    "pacing_rationale": "Single concept.",
    "periods": [
        {
            "period_number": 1,
            "duration_minutes": 40,
            "title": "Force",
            "learning_objectives": ["Define force."],
            "concepts_covered": ["Force"],
            "summary": "Intro to force.",
        }
    ],
}

_ITEMS_RESPONSE = {"items": [{"period_number": 1, "question": "What is force?", "expected_answer": "A push or pull."}]}

_ASSESSMENT_RESPONSE = {
    "mcqs": [
        {
            "question": "What is force?",
            "options": ["A push or pull", "A color"],
            "correct_option": "A push or pull",
            "explanation": "Definition.",
        }
    ],
    "short_answer": [],
    "long_answer": [],
    "numerical": [],
    "rubric": "1 mark per MCQ.",
}

_GUIDANCE_RESPONSE = {
    "misconception_guidance": [],
    "teaching_tips": ["Use everyday examples."],
    "pacing_notes": "One period suffices.",
}

_CLASSROOM_ACTIVITY_RESPONSE = {
    "items": [
        {
            "period_number": 1,
            "title": "Push or Pull Demo",
            "activity_type": "demonstration",
            "duration_minutes": 15,
            "materials_needed": ["a small box"],
            "instructions": "Push and pull the box to show force in action.",
            "success_criteria": "Students can identify the direction of applied force.",
        }
    ]
}


def test_orchestrator_isolates_a_single_module_failure():
    class _SelectivelyFailingLLM:
        def generate_json(self, prompt):
            if "Lesson Planner" in prompt:
                raise LLMGenerationError("lesson planner is down")
            if "Assessment" in prompt:
                return _ASSESSMENT_RESPONSE
            if "Teacher Guidance" in prompt:
                return _GUIDANCE_RESPONSE
            if "Classroom Activity" in prompt:
                return _CLASSROOM_ACTIVITY_RESPONSE
            return _ITEMS_RESPONSE

    orchestrator = TeachingPackageOrchestrator(llm_provider=_SelectivelyFailingLLM())
    package = orchestrator.generate(_sample_knowledge(), _sample_metadata())

    # The failing module is recorded, not raised.
    assert package.lesson_plan is None
    assert "lesson_plan" in package.generation_errors

    # Every other module still succeeded.
    assert package.assessment is not None
    assert package.teacher_guidance is not None
    assert package.entry_ticket is not None
    assert package.exit_ticket is not None
    assert package.homework is not None
    assert package.teacher_script is not None
    assert package.blackboard_notes is not None
    assert package.classroom_activity is not None

    assert set(package.modules_generated()) == {
        "entry_ticket", "teacher_script", "blackboard_notes", "classroom_activity",
        "assessment", "exit_ticket", "homework", "teacher_guidance",
    }
    assert package.modules_failed() == ["lesson_plan"]
    assert package.document_id == "doc-1"


def test_orchestrator_succeeds_fully_when_all_modules_succeed():
    class _AllSucceedLLM:
        def generate_json(self, prompt):
            if "Lesson Planner" in prompt:
                return _LESSON_PLAN_RESPONSE
            if "Assessment" in prompt:
                return _ASSESSMENT_RESPONSE
            if "Teacher Guidance" in prompt:
                return _GUIDANCE_RESPONSE
            if "Classroom Activity" in prompt:
                return _CLASSROOM_ACTIVITY_RESPONSE
            return _ITEMS_RESPONSE

    orchestrator = TeachingPackageOrchestrator(llm_provider=_AllSucceedLLM())
    package = orchestrator.generate(_sample_knowledge(), _sample_metadata())

    assert package.generation_errors == {}
    assert len(package.modules_generated()) == 9
    assert package.lesson_plan.total_periods == 1
