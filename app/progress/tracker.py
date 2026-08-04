"""
Progress tracking for long-running ingestion jobs.

Phase 1A uses a simple in-process, thread-safe in-memory store keyed
by job id. This deliberately keeps the same public interface
(``create_job`` / ``update_stage`` / ``get_job``) that a Phase 1B
Redis- or DB-backed tracker would expose, so swapping the backend
later does not require touching any caller.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.constants import TERMINAL_STAGES, JobStage
from app.core.exceptions import JobNotFoundError

logger = logging.getLogger(__name__)


class JobProgress(BaseModel):
    job_id: str
    stage: JobStage = JobStage.QUEUED
    progress: int = Field(ge=0, le=100, default=0)
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: Optional[dict] = None

    @property
    def is_terminal(self) -> bool:
        return self.stage in TERMINAL_STAGES


_STAGE_PROGRESS: dict[JobStage, int] = {
    JobStage.QUEUED: 0,
    JobStage.ROUTING: 10,
    JobStage.PARSING: 28,
    JobStage.STRUCTURING: 40,
    JobStage.CHUNKING: 52,
    JobStage.EMBEDDING: 64,
    JobStage.INDEXING: 74,
    JobStage.CLASSIFYING: 84,
    JobStage.EXTRACTING_KNOWLEDGE: 94,
    JobStage.GENERATING_PACKAGE: 97,
    JobStage.COMPLETED: 100,
    JobStage.FAILED: 100,
}


class ProgressTracker:
    """Thread-safe in-memory job progress store."""

    def __init__(self) -> None:
        self._jobs: Dict[str, JobProgress] = {}
        self._lock = threading.Lock()

    def create_job(self) -> JobProgress:
        job = JobProgress(job_id=uuid4().hex)
        with self._lock:
            self._jobs[job.job_id] = job
        logger.info("Created job %s", job.job_id)
        return job

    def update_stage(
        self,
        job_id: str,
        stage: JobStage,
        message: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[dict] = None,
    ) -> JobProgress:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"No job found with id {job_id}")
            job.stage = stage
            job.progress = _STAGE_PROGRESS.get(stage, job.progress)
            job.message = message
            job.error = error
            if result is not None:
                job.result = result
            job.updated_at = datetime.now(timezone.utc)
            self._jobs[job_id] = job
        logger.info("Job %s -> stage=%s progress=%d%%", job_id, stage.value, job.progress)
        return job

    def get_job(self, job_id: str) -> JobProgress:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"No job found with id {job_id}")
        return job


# Process-wide singleton - simple and sufficient for Phase 1A's single-worker scope.
progress_tracker = ProgressTracker()
