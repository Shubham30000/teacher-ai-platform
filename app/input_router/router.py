"""
Input Router (PROJECT_ROADMAP.md item 3).

A single entry point that accepts an uploaded file, decides how to
handle it, and dispatches to the correct downstream pipeline stage - it
never parses/interprets content itself.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from app.core.constants import EXTENSION_TO_FILE_TYPE, InputMode
from app.document_intelligence.models import StructuredDocument
from app.parsers.factory import ParserFactory

logger = logging.getLogger(__name__)


class RoutingRequest(BaseModel):
    """``file_path`` must be provided."""

    file_path: Optional[Path] = None


class RoutingResult(BaseModel):
    """Outcome of routing: either a ready StructuredDocument, or a request for more info."""

    mode: InputMode
    structured_document: Optional[StructuredDocument] = None
    needs_clarification: bool = False
    clarification_message: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}


class InputRouter:
    """Routes a request to file parsing."""

    def route(self, request: RoutingRequest) -> RoutingResult:
        if request.file_path:
            return self._route_file_upload(request.file_path)
        raise ValueError("file_path must be provided.")

    def _route_file_upload(self, file_path: Path) -> RoutingResult:
        extension = file_path.suffix.lower()
        if extension not in EXTENSION_TO_FILE_TYPE:
            return RoutingResult(
                mode=InputMode.FILE_UPLOAD,
                needs_clarification=True,
                clarification_message=(
                    f"'{extension}' is not a supported file type. "
                    f"Please upload one of: {', '.join(EXTENSION_TO_FILE_TYPE)}."
                ),
            )
        logger.info("Routing file upload '%s' to %s parser", file_path.name, extension)
        parser = ParserFactory.get_parser(file_path)
        structured_document = parser.parse(file_path)
        return RoutingResult(mode=InputMode.FILE_UPLOAD, structured_document=structured_document)
