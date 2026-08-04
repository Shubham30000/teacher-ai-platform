"""
The nine Phase 2A Teaching Package generators.

Each class is a thin subclass of :class:`BaseTeachingGenerator`: it
points at its own prompt template under ``prompts/`` and knows how to
turn that prompt's JSON response into its own output model from
``app.teaching_package.models``.
"""
from __future__ import annotations

from typing import Any

from app.teaching_package.base import BaseTeachingGenerator
from app.teaching_package.models import (
    Assessment,
    BlackboardNotes,
    ClassroomActivity,
    EntryTicket,
    ExitTicket,
    Homework,
    LessonPlan,
    TeacherGuidance,
    TeacherScript,
)


class LessonPlanGenerator(BaseTeachingGenerator):
    prompt_name = "lesson_planner_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> LessonPlan:
        return LessonPlan(
            total_periods=int(raw.get("total_periods", 0) or len(raw.get("periods", []) or [])),
            pacing_rationale=raw.get("pacing_rationale", "") or "",
            periods=raw.get("periods", []) or [],
        )


class EntryTicketGenerator(BaseTeachingGenerator):
    prompt_name = "entry_ticket_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> EntryTicket:
        return EntryTicket(items=raw.get("items", []) or [])


class TeacherScriptGenerator(BaseTeachingGenerator):
    prompt_name = "teacher_script_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> TeacherScript:
        return TeacherScript(items=raw.get("items", []) or [])


class BlackboardNotesGenerator(BaseTeachingGenerator):
    prompt_name = "blackboard_notes_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> BlackboardNotes:
        return BlackboardNotes(items=raw.get("items", []) or [])


class ClassroomActivityGenerator(BaseTeachingGenerator):
    prompt_name = "classroom_activity_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> ClassroomActivity:
        return ClassroomActivity(items=raw.get("items", []) or [])


class AssessmentGenerator(BaseTeachingGenerator):
    prompt_name = "assessment_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> Assessment:
        return Assessment(
            mcqs=raw.get("mcqs", []) or [],
            short_answer=raw.get("short_answer", []) or [],
            long_answer=raw.get("long_answer", []) or [],
            numerical=raw.get("numerical", []) or [],
            rubric=raw.get("rubric", "") or "",
        )


class ExitTicketGenerator(BaseTeachingGenerator):
    prompt_name = "exit_ticket_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> ExitTicket:
        return ExitTicket(items=raw.get("items", []) or [])


class HomeworkGenerator(BaseTeachingGenerator):
    prompt_name = "homework_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> Homework:
        return Homework(items=raw.get("items", []) or [])


class TeacherGuidanceGenerator(BaseTeachingGenerator):
    prompt_name = "teacher_guidance_prompt.md"

    def _parse(self, raw: dict[str, Any]) -> TeacherGuidance:
        return TeacherGuidance(
            motivation_of_the_day=raw.get("motivation_of_the_day", "") or "",
            key_takeaway=raw.get("key_takeaway", "") or "",
            misconception_guidance=raw.get("misconception_guidance", []) or [],
            teaching_tips=[str(t) for t in (raw.get("teaching_tips", []) or [])],
            support_for_struggling_learners=[
                str(t) for t in (raw.get("support_for_struggling_learners", []) or [])
            ],
            challenge_for_advanced_learners=[
                str(t) for t in (raw.get("challenge_for_advanced_learners", []) or [])
            ],
            common_mistakes=[str(t) for t in (raw.get("common_mistakes", []) or [])],
            time_management_advice=[
                str(t) for t in (raw.get("time_management_advice", []) or [])
            ],
            pacing_notes=raw.get("pacing_notes", "") or "",
        )
