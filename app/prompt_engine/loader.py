"""
Prompt template loader (PROJECT_ROADMAP.md item 12.1).

Prompts are versioned Markdown artifacts under ``<repo_root>/prompts/``,
never embedded as inline strings inside business logic. This module is
the single place that reads those files and fills in ``{{VARIABLE}}``
placeholders - callers (``EducationalClassifier``, ``KnowledgeExtractor``)
only ever import :func:`render_prompt`, never touch the filesystem
themselves.

``{{VARIABLE}}`` (double curly braces) is used instead of ``str.format``
style ``{variable}`` specifically because the prompt templates contain
literal JSON output-format examples full of ``{`` / ``}`` characters -
``str.format`` would collide with those and require escaping every
brace in the template.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from app.config import get_settings
from app.core.exceptions import PromptLoadError

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


@lru_cache(maxsize=None)
def _read_template(name: str) -> str:
    settings = get_settings()
    path: Path = settings.prompts_dir / name
    if not path.is_file():
        raise PromptLoadError(f"Prompt template not found: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise PromptLoadError(f"Prompt template is empty: {path}")
    return text


def load_prompt_template(name: str) -> str:
    """Return the raw contents of ``prompts/<name>``, cached after first read."""
    return _read_template(name)


def render_prompt(name: str, variables: Mapping[str, str]) -> str:
    """Load ``prompts/<name>`` and substitute every ``{{VARIABLE}}`` placeholder.

    Raises :class:`PromptLoadError` if the template references a
    placeholder that was not supplied in ``variables`` - a missing
    variable would otherwise silently ship a literal ``{{PLACEHOLDER}}``
    string to the model.
    """
    template = load_prompt_template(name)

    required = set(_PLACEHOLDER_RE.findall(template))
    missing = required - set(variables.keys())
    if missing:
        raise PromptLoadError(
            f"Prompt template '{name}' is missing values for placeholders: {sorted(missing)}"
        )

    def _substitute(match: "re.Match[str]") -> str:
        key = match.group(1)
        return str(variables[key])

    return _PLACEHOLDER_RE.sub(_substitute, template)


def clear_prompt_cache() -> None:
    """Test-only helper to force templates to be re-read from disk."""
    _read_template.cache_clear()
