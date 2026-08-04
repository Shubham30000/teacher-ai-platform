"""Pydantic request/response schemas for the FastAPI layer."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.constants import InputMode, JobStage


class HealthResponse(BaseModel):
    status: str = "ok"
    app_name: str
    app_env: str


class KnowledgeJSONSummary(BaseModel):
    """Item counts only - the API surfaces a summary, not the full KnowledgeJSON,
    to keep the upload response lightweight. Fetch the full object via a
    future dedicated endpoint if needed (out of scope for Phase 1B)."""

    learning_objectives: int = 0
    concepts: int = 0
    definitions: int = 0
    formulae: int = 0
    examples: int = 0
    applications: int = 0
    misconceptions: int = 0


class TeachingPackageSummary(BaseModel):
    """Item counts / status only - mirrors KnowledgeJSONSummary's role of
    keeping the /upload response lightweight. Fetch the full
    TeachingPackage via GET /teaching-package/{document_id}."""

    modules_generated: List[str] = Field(default_factory=list)
    modules_failed: List[str] = Field(default_factory=list)
    total_periods: Optional[int] = None


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    mode: InputMode = InputMode.FILE_UPLOAD
    document_id: Optional[str] = None
    section_count: Optional[int] = None
    chunk_count: Optional[int] = None
    stage: JobStage
    needs_clarification: bool = False
    clarification_message: Optional[str] = None
    document_metadata: Optional[Dict[str, Any]] = None
    knowledge_summary: Optional[KnowledgeJSONSummary] = None
    teaching_package_summary: Optional[TeachingPackageSummary] = None


class ProgressResponse(BaseModel):
    job_id: str
    stage: JobStage
    progress: int
    message: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_id: Optional[str] = None


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    text: str
    heading_path: str
    page_number: int
    similarity_score: float


class RetrievalResponse(BaseModel):
    query: str
    results: List[RetrievedChunkResponse]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
