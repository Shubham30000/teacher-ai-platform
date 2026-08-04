"""Teaching Package endpoint (Phase 2A, PROJECT_ROADMAP.md)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.exceptions import TeachingPackageNotFoundError
from app.teaching_package.models import TeachingPackage
from app.teaching_package.persistence import load_teaching_package

router = APIRouter(tags=["teaching-package"])


@router.get("/teaching-package/{document_id}", response_model=TeachingPackage)
def get_teaching_package(document_id: str) -> TeachingPackage:
    try:
        return load_teaching_package(document_id)
    except TeachingPackageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
