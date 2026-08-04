"""Upload endpoints - PROJECT_ROADMAP.md item 2 (Upload endpoint).

``POST /upload`` is the original Phase 2A API contract: it blocks until the
entire ingestion + teaching-package pipeline has finished and returns the
complete result in one response (document_id, metadata, knowledge_summary,
teaching_package_summary). This is the endpoint documented in Swagger and
used by any external/API caller.

During Phase 2B this endpoint was changed to return immediately and run the
pipeline in a background task, so the browser Progress page could poll
``GET /api/v1/progress/{job_id}`` for real progress. That behavior change
broke the documented API contract, so it has been split out into its own
endpoint instead: ``POST /upload/web``. That endpoint is used only by the
server-rendered frontend (see ``static/js/upload.js``) and behaves exactly
like the Phase 2B upload did - it returns a job_id immediately and the
pipeline (including teaching package generation) runs afterwards, with
progress and the final result available via ``GET /api/v1/progress/{job_id}``.

No stage's internal pipeline logic changes between the two endpoints - they
both call the same ``run_ingestion`` / teaching package generation code,
just synchronously vs. via a FastAPI BackgroundTask.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.core.constants import JobStage
from app.core.exceptions import (
    FileTooLargeError,
    ParsingError,
    TeacherPlatformError,
    UnsupportedFileTypeError,
)
from app.ingestion_service import run_ingestion
from app.models.schemas import KnowledgeJSONSummary, TeachingPackageSummary, UploadResponse
from app.progress.tracker import progress_tracker
from app.teaching_package.orchestrator import TeachingPackageOrchestrator
from app.teaching_package.persistence import save_teaching_package
from app.utils.file_utils import save_upload_bytes

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    """Phase 2A behavior (restored): waits for the full pipeline to finish
    before returning the complete result."""
    content = await file.read()

    try:
        saved_path = save_upload_bytes(file.filename or "upload", content)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    job = progress_tracker.create_job()
    logger.info("Upload job %s created for '%s'", job.job_id, file.filename)

    try:
        outcome = run_ingestion(job.job_id, progress_tracker, file_path=saved_path)
    except ParsingError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except TeacherPlatformError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc

    routing_result = outcome.routing_result
    document = routing_result.structured_document

    teaching_package_summary = None
    if outcome.document_metadata is not None and outcome.knowledge_json is not None:
        teaching_package_summary = _generate_teaching_package(
            outcome.document_metadata, outcome.knowledge_json
        )

    return UploadResponse(
        job_id=job.job_id,
        filename=file.filename or saved_path.name,
        document_id=document.document_id if document else None,
        section_count=len(document.all_sections_flat()) if document else None,
        chunk_count=outcome.chunk_count,
        stage=progress_tracker.get_job(job.job_id).stage,
        needs_clarification=routing_result.needs_clarification,
        clarification_message=routing_result.clarification_message,
        document_metadata=(
            outcome.document_metadata.model_dump(mode="json") if outcome.document_metadata else None
        ),
        knowledge_summary=(
            KnowledgeJSONSummary(
                learning_objectives=len(outcome.knowledge_json.learning_objectives),
                concepts=len(outcome.knowledge_json.concepts),
                definitions=len(outcome.knowledge_json.definitions),
                formulae=len(outcome.knowledge_json.formulae),
                examples=len(outcome.knowledge_json.examples),
                applications=len(outcome.knowledge_json.applications),
                misconceptions=len(outcome.knowledge_json.misconceptions),
            )
            if outcome.knowledge_json
            else None
        ),
        teaching_package_summary=teaching_package_summary,
    )


@router.post("/upload/web", response_model=UploadResponse)
async def upload_document_web(file: UploadFile = File(...), background_tasks: BackgroundTasks = None) -> UploadResponse:
    """Frontend-only upload path (see module docstring). Returns immediately
    with a queued job_id; the pipeline runs in a background task and the
    Progress page polls ``GET /api/v1/progress/{job_id}`` for updates and
    the final result."""
    content = await file.read()

    try:
        saved_path = save_upload_bytes(file.filename or "upload", content)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    job = progress_tracker.create_job()
    logger.info("Web upload job %s created for '%s'", job.job_id, file.filename)

    background_tasks.add_task(_process_upload_job, job.job_id, saved_path, file.filename or saved_path.name)

    return UploadResponse(
        job_id=job.job_id,
        filename=file.filename or saved_path.name,
        stage=job.stage,
    )


def _process_upload_job(job_id: str, saved_path, filename: str) -> None:
    """Runs off the request/response cycle for ``/upload/web`` (see module
    docstring). Any failure here is already recorded on the job by
    ``run_ingestion`` (which sets JobStage.FAILED before re-raising), so
    this wrapper only needs to stop the exception from propagating into the
    background-task runner."""
    try:
        outcome = run_ingestion(job_id, progress_tracker, file_path=saved_path, mark_completed=False)
    except TeacherPlatformError:
        logger.warning("Upload job %s failed during ingestion", job_id)
        return
    except Exception:  # noqa: BLE001 - already logged/recorded by run_ingestion
        logger.exception("Upload job %s failed unexpectedly during ingestion", job_id)
        return

    routing_result = outcome.routing_result
    document = routing_result.structured_document

    if routing_result.needs_clarification or outcome.document_metadata is None or outcome.knowledge_json is None:
        # run_ingestion already marked the job COMPLETED with a
        # needs_clarification result (or there is nothing further to do).
        return

    progress_tracker.update_stage(job_id, JobStage.GENERATING_PACKAGE, "Generating teaching package")
    teaching_package_summary = _generate_teaching_package(outcome.document_metadata, outcome.knowledge_json)

    progress_tracker.update_stage(
        job_id,
        JobStage.COMPLETED,
        message="Teaching package ready.",
        result={
            "job_id": job_id,
            "filename": filename,
            "document_id": document.document_id if document else None,
            "section_count": len(document.all_sections_flat()) if document else None,
            "chunk_count": outcome.chunk_count,
            "stage": JobStage.COMPLETED.value,
            "needs_clarification": False,
            "clarification_message": None,
            "document_metadata": outcome.document_metadata.model_dump(mode="json"),
            "knowledge_summary": KnowledgeJSONSummary(
                learning_objectives=len(outcome.knowledge_json.learning_objectives),
                concepts=len(outcome.knowledge_json.concepts),
                definitions=len(outcome.knowledge_json.definitions),
                formulae=len(outcome.knowledge_json.formulae),
                examples=len(outcome.knowledge_json.examples),
                applications=len(outcome.knowledge_json.applications),
                misconceptions=len(outcome.knowledge_json.misconceptions),
            ).model_dump(mode="json"),
            "teaching_package_summary": (
                teaching_package_summary.model_dump(mode="json") if teaching_package_summary else None
            ),
        },
    )


def _generate_teaching_package(document_metadata, knowledge_json) -> TeachingPackageSummary | None:
    """Run Phase 2A generation + persistence for a just-ingested document.

    Isolated in its own try/except so a Teaching Package failure never
    fails the caller - ingestion has already succeeded and should still be
    reported back (either directly in the response, for ``/upload``, or on
    the job's result, for ``/upload/web``).
    """
    try:
        package = TeachingPackageOrchestrator().generate(knowledge_json, document_metadata)
        save_teaching_package(document_metadata, knowledge_json, package)
        return TeachingPackageSummary(
            modules_generated=package.modules_generated(),
            modules_failed=package.modules_failed(),
            total_periods=package.lesson_plan.total_periods if package.lesson_plan else None,
        )
    except TeacherPlatformError as exc:
        logger.warning(
            "Teaching Package generation failed for document %s: %s",
            document_metadata.document_id, exc.message,
        )
        return TeachingPackageSummary(modules_failed=["all"])
