"""Filesystem helper utilities for uploads."""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError

_UNSAFE_CHARS_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


def sanitize_filename(filename: str) -> str:
    """Strip path components and unsafe characters from a client-supplied filename."""
    name = Path(filename).name
    stem, ext = Path(name).stem, Path(name).suffix
    safe_stem = _UNSAFE_CHARS_RE.sub("_", stem).strip("_") or "file"
    return f"{safe_stem}{ext.lower()}"


def validate_upload(filename: str, size_bytes: int) -> None:
    settings = get_settings()
    extension = Path(filename).suffix.lower()
    if extension not in settings.allowed_extensions:
        raise UnsupportedFileTypeError(
            f"'{extension}' is not supported. Allowed: {', '.join(settings.allowed_extensions)}"
        )
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileTooLargeError(
            f"File is {size_bytes / (1024 * 1024):.1f}MB, exceeds the "
            f"{settings.max_upload_size_mb}MB limit."
        )


def unique_upload_path(filename: str) -> Path:
    """Build a collision-free destination path under the configured upload directory."""
    settings = get_settings()
    safe_name = sanitize_filename(filename)
    stem, ext = Path(safe_name).stem, Path(safe_name).suffix
    destination = settings.upload_dir / f"{stem}_{uuid4().hex[:8]}{ext}"
    return destination


def save_upload_bytes(filename: str, content: bytes) -> Path:
    """Validate and persist uploaded bytes; returns the saved path."""
    validate_upload(filename, len(content))
    destination = unique_upload_path(filename)
    destination.write_bytes(content)
    return destination
