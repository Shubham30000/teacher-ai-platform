"""
Teaching Package data contracts (Phase 2A, PROJECT_ROADMAP.md).

Every model here is produced from an already-generated ``KnowledgeJSON``
+ ``DocumentMetadata`` (Phase 1B) - no new knowledge is extracted from
the source document at this stage, per the Phase 2A objective. Each
module returns a small, self-contained Pydantic model; ``TeachingPackage``
aggregates all nine into the single object persisted and served by the
API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class LessonPeriod(BaseModel):
    period_number: int
    duration_minutes: int
    title: str
    learning_objectives: List[str] = Field(default_factory=list)
    concepts_covered: List[str] = Field(default_factory=list)
    summary: str = ""


class LessonPlan(BaseModel):
    total_periods: int
    pacing_rationale: str = ""
    periods: List[LessonPeriod] = Field(default_factory=list)


class EntryTicketItem(BaseModel):
    period_number: int
    question: str
    expected_answer: str = ""
    duration_minutes: int = 5


class EntryTicket(BaseModel):
    items: List[EntryTicketItem] = Field(default_factory=list)


class TeacherScriptItem(BaseModel):
    period_number: int
    introduction: str = ""
    explanation: str = ""
    closure: str = ""
    mentor_moment: str = ""


class TeacherScript(BaseModel):
    items: List[TeacherScriptItem] = Field(default_factory=list)


class BlackboardNoteItem(BaseModel):
    period_number: int
    bullet_points: List[str] = Field(default_factory=list)
    diagrams_or_equations: List[str] = Field(default_factory=list)


class BlackboardNotes(BaseModel):
    items: List[BlackboardNoteItem] = Field(default_factory=list)


class ClassroomActivityItem(BaseModel):
    period_number: int
    title: str
    activity_type: str = ""
    duration_minutes: int = 15
    materials_needed: List[str] = Field(default_factory=list)
    instructions: str = ""
    success_criteria: str = ""


class ClassroomActivity(BaseModel):
    items: List[ClassroomActivityItem] = Field(default_factory=list)


class MCQItem(BaseModel):
    question: str
    options: List[str] = Field(default_factory=list)
    correct_option: str = ""
    explanation: str = ""


class ShortAnswerItem(BaseModel):
    question: str
    answer: str = ""


class NumericalItem(BaseModel):
    question: str
    solution: str = ""


class Assessment(BaseModel):
    mcqs: List[MCQItem] = Field(default_factory=list)
    short_answer: List[ShortAnswerItem] = Field(default_factory=list)
    long_answer: List[ShortAnswerItem] = Field(default_factory=list)
    numerical: List[NumericalItem] = Field(default_factory=list)
    rubric: str = ""


class ExitTicketItem(BaseModel):
    period_number: int
    question: str
    expected_answer: str = ""


class ExitTicket(BaseModel):
    items: List[ExitTicketItem] = Field(default_factory=list)


class HomeworkItem(BaseModel):
    period_number: int
    tasks: List[str] = Field(default_factory=list)


class Homework(BaseModel):
    items: List[HomeworkItem] = Field(default_factory=list)


class MisconceptionGuidance(BaseModel):
    """One entry of the Learning Gap Analysis (assignment Stage 8)."""

    misconception: str
    diagnostic_question: str = ""
    remedial_action: str = ""
    severity: str = "low"  # "low" | "medium" | "high"


class TeacherGuidance(BaseModel):
    motivation_of_the_day: str = ""
    key_takeaway: str = ""
    misconception_guidance: List[MisconceptionGuidance] = Field(default_factory=list)
    teaching_tips: List[str] = Field(default_factory=list)
    support_for_struggling_learners: List[str] = Field(default_factory=list)
    challenge_for_advanced_learners: List[str] = Field(default_factory=list)
    common_mistakes: List[str] = Field(default_factory=list)
    time_management_advice: List[str] = Field(default_factory=list)
    pacing_notes: str = ""


MODULE_NAMES = (
    "lesson_plan",
    "entry_ticket",
    "teacher_script",
    "blackboard_notes",
    "classroom_activity",
    "assessment",
    "exit_ticket",
    "homework",
    "teacher_guidance",
)


class TeachingPackage(BaseModel):
    """The complete Phase 2A output for one document.

    Any module that failed to generate is left ``None`` and recorded in
    ``generation_errors`` rather than aborting the whole package -
    per the orchestrator's "handle failures independently" requirement.
    """

    document_id: str
    lesson_plan: Optional[LessonPlan] = None
    entry_ticket: Optional[EntryTicket] = None
    teacher_script: Optional[TeacherScript] = None
    blackboard_notes: Optional[BlackboardNotes] = None
    classroom_activity: Optional[ClassroomActivity] = None
    assessment: Optional[Assessment] = None
    exit_ticket: Optional[ExitTicket] = None
    homework: Optional[Homework] = None
    teacher_guidance: Optional[TeacherGuidance] = None
    generation_errors: Dict[str, str] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def modules_generated(self) -> List[str]:
        return [name for name in MODULE_NAMES if getattr(self, name) is not None]

    def modules_failed(self) -> List[str]:
        return list(self.generation_errors.keys())
