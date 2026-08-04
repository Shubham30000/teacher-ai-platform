"""
FastAPI application entry point (PROJECT_ROADMAP.md item 2).

Run locally with:

    uvicorn app.main:app --reload

Phase 1A exposes exactly the endpoints the roadmap specifies: health,
upload, and progress - plus a ``/api/v1/retrieve`` endpoint so
the retriever built in item 11 is reachable and testable end-to-end,
without adding any lesson-generation surface area.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import export, health, progress, teaching_package, upload
from app.config import BASE_DIR, get_settings
from app.core.exceptions import RetrievalError, TeacherPlatformError
from app.logging_config import configure_logging
from app.models.schemas import ErrorResponse, RetrievalRequest, RetrievalResponse, RetrievedChunkResponse
from app.retriever.retriever import Retriever
from app.web.routes import render_404
from app.web.routes import router as web_router

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Document ingestion, retrieval, and Teaching Package generation "
        "for the AI-powered Teacher Knowledge Package platform "
        "(Phase 1: ingestion/knowledge extraction, Phase 2A: Teaching Package generation)."
    ),
    version="2A.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(TeacherPlatformError)
async def teacher_platform_error_handler(request, exc: TeacherPlatformError):
    from fastapi.responses import JSONResponse

    logger.error("Unhandled TeacherPlatformError: %s", exc.message)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error=type(exc).__name__, detail=exc.message).model_dump(),
    )


app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(upload.router, prefix=settings.api_v1_prefix)
app.include_router(progress.router, prefix=settings.api_v1_prefix)
app.include_router(teaching_package.router, prefix=settings.api_v1_prefix)
app.include_router(export.router, prefix=settings.api_v1_prefix)

# --- Phase 2B: browser-facing UI (server-rendered pages + static assets) ---
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(web_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """Render a friendly 404 page for browser navigation; keep JSON errors
    for API requests and any other HTTP status."""
    if exc.status_code == 404 and not request.url.path.startswith(settings.api_v1_prefix):
        return render_404(request)
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.post(f"{settings.api_v1_prefix}/retrieve", response_model=RetrievalResponse, tags=["retrieve"])
def retrieve(request: RetrievalRequest) -> RetrievalResponse:
    """Query the vector store built by /upload. Exists to make item 11
    (Retriever) directly testable via the API, not only via internal calls."""
    retriever = Retriever()
    try:
        results = retriever.retrieve(request.query, top_k=request.top_k, document_id=request.document_id)
    except RetrievalError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return RetrievalResponse(
        query=request.query,
        results=[
            RetrievedChunkResponse(
                chunk_id=r.chunk_id,
                text=r.text,
                heading_path=r.heading_path,
                page_number=r.page_number,
                similarity_score=r.similarity_score,
            )
            for r in results
        ],
    )

