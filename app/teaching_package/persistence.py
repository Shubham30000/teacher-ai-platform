"""
Teaching Package persistence (Phase 2A).

Persists ``DocumentMetadata`` + ``KnowledgeJSON`` + ``TeachingPackage``
as a single JSON file per document under ``settings.outputs_dir``, per
the Phase 2A roadmap's "no database" requirement. One file per
document keeps this readable without introducing new storage
machinery - a natural extension of the plain-file conventions already
used for uploads (``app.utils.file_utils``).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.classification.models import DocumentMetadata
from app.config import get_settings
from app.core.exceptions import TeachingPackageNotFoundError
from app.knowledge_extraction.models import KnowledgeJSON
from app.teaching_package.models import TeachingPackage


def _bundle_path(document_id: str) -> Path:
    settings = get_settings()
    return settings.outputs_dir / f"{document_id}.json"


def save_teaching_package(
    document_metadata: DocumentMetadata,
    knowledge_json: KnowledgeJSON,
    teaching_package: TeachingPackage,
) -> Path:
    """Persist the full bundle for one document and return the file path."""
    settings = get_settings()
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "document_metadata": document_metadata.model_dump(mode="json"),
        "knowledge_json": knowledge_json.model_dump(mode="json"),
        "teaching_package": teaching_package.model_dump(mode="json"),
    }
    path = _bundle_path(teaching_package.document_id)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_teaching_package(document_id: str) -> TeachingPackage:
    """Load the persisted TeachingPackage for ``document_id``.

    Raises :class:`TeachingPackageNotFoundError` if nothing was ever
    persisted for that document.
    """
    return TeachingPackage(**load_teaching_bundle(document_id)["teaching_package"])


def load_teaching_bundle(document_id: str) -> dict:
    """Load the full persisted bundle (metadata + knowledge_json + teaching_package)
    for ``document_id`` as a plain dict.

    Used by the Phase 2B export endpoints (JSON/PDF/DOCX download) so they can
    read the already-persisted, already-generated content without re-running
    any generation logic. Raises :class:`TeachingPackageNotFoundError` if
    nothing was ever persisted for that document.
    """
    path = _bundle_path(document_id)
    if not path.is_file():
        raise TeachingPackageNotFoundError(
            f"No Teaching Package found for document_id '{document_id}'"
        )
    return json.loads(path.read_text(encoding="utf-8"))
