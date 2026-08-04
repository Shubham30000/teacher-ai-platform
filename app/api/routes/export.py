"""
Export endpoints (Phase 2B).

The assignment's Stage 10 ("Publishing") calls for "easily consumable
formats" (PDFs, etc.) alongside the master TeacherKnowledgePackage.json.
Phase 2A already persists that full bundle per document via
``app.teaching_package.persistence``; these routes only *read* that
already-generated content and format it for download - they never call
an LLM and never touch the generation pipeline.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response

from app.core.exceptions import TeachingPackageNotFoundError
from app.teaching_package.persistence import load_teaching_bundle
from app.utils.export_utils import render_docx_bytes, render_pdf_bytes

router = APIRouter(tags=["export"])


def _load_bundle_or_404(document_id: str) -> dict:
    try:
        return load_teaching_bundle(document_id)
    except TeachingPackageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.get("/export/{document_id}/json")
def export_json(document_id: str) -> JSONResponse:
    bundle = _load_bundle_or_404(document_id)
    return JSONResponse(
        content=bundle,
        headers={
            "Content-Disposition": f'attachment; filename="{document_id}_teaching_package.json"'
        },
    )


@router.get("/export/{document_id}/docx")
def export_docx(document_id: str) -> Response:
    bundle = _load_bundle_or_404(document_id)
    content = render_docx_bytes(bundle)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{document_id}_teaching_package.docx"'
        },
    )


@router.get("/export/{document_id}/pdf")
def export_pdf(document_id: str) -> Response:
    bundle = _load_bundle_or_404(document_id)
    content = render_pdf_bytes(bundle)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{document_id}_teaching_package.pdf"'
        },
    )
