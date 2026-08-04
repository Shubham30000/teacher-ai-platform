"""
Progress endpoint (PROJECT_ROADMAP.md item 2 / assignment's "Streaming Progress API").

Phase 1A's ingestion runs synchronously within the request/response
cycle of ``/upload`` (there is no lesson generation yet,
so a single document's pipeline completes in seconds), so this endpoint
exposes the same ``JobProgress`` state via polling. A Server-Sent-Events
variant is included for forward compatibility with Phase 1B's
long-running generation jobs, where ``{"stage": ..., "progress": ...}``
events genuinely need to stream rather than be polled.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.constants import TERMINAL_STAGES
from app.core.exceptions import JobNotFoundError
from app.models.schemas import ProgressResponse
from app.progress.tracker import progress_tracker

router = APIRouter(tags=["progress"])


@router.get("/progress/{job_id}", response_model=ProgressResponse)
def get_progress(job_id: str) -> ProgressResponse:
    try:
        job = progress_tracker.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return ProgressResponse(
        job_id=job.job_id,
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        error=job.error,
        result=job.result,
    )


@router.get("/progress/{job_id}/stream")
async def stream_progress(job_id: str) -> StreamingResponse:
    try:
        progress_tracker.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    async def event_generator():
        last_stage = None
        while True:
            job = progress_tracker.get_job(job_id)
            if job.stage != last_stage:
                payload = {"stage": job.stage.value, "progress": job.progress, "message": job.message}
                yield f"data: {json.dumps(payload)}\n\n"
                last_stage = job.stage
            if job.stage in TERMINAL_STAGES:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
