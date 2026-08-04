"""
Browser-facing page routes (Phase 2B).

These render the Jinja2 templates that make up the teacher-facing UI.
They never talk to the AI pipeline directly - all data comes from the
existing ``/api/v1`` endpoints via client-side JavaScript (see
``static/js/``). This module only decides which HTML shell to render
for a given URL.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, get_settings

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(include_in_schema=False)


def _settings_context() -> dict:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "max_upload_size_mb": settings.max_upload_size_mb,
    }


@router.get("/", response_class=HTMLResponse)
def home_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "home.html", _settings_context()
    )


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "upload.html", _settings_context()
    )


@router.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "progress.html", _settings_context()
    )


@router.get("/results/{document_id}", response_class=HTMLResponse)
def results_page(request: Request, document_id: str) -> HTMLResponse:
    context = _settings_context()
    context["document_id"] = document_id
    return templates.TemplateResponse(request, "results.html", context)


@router.get("/error", response_class=HTMLResponse)
def error_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "error.html", _settings_context()
    )


def render_404(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "404.html", _settings_context(), status_code=404
    )
