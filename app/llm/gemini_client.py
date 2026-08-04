"""
Gemini text-generation client (Phase 1B).

Mirrors the structure of ``app.embeddings.gemini_embeddings`` on
purpose: a thin, swappable provider class behind a small ``Protocol``
interface so that Educational Classification and Knowledge Extraction
never talk to the ``google-genai`` SDK directly - only to this
module. This keeps both callers unit-testable via dependency injection
(``monkeypatch.setattr(provider, "_ensure_client", ...)``), the same
pattern already used by ``GeminiEmbeddingProvider``.

Structured JSON output is requested via ``response_mime_type =
"application/json"``; the parser additionally strips Markdown code
fences as a defensive fallback for models that ignore the MIME hint.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional, Protocol

from app.config import get_settings
from app.core.exceptions import LLMGenerationError

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 1.5

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class TextGenerationProvider(Protocol):
    """Interface any structured-JSON-generation backend must satisfy."""

    def generate_json(self, prompt: str) -> dict[str, Any]: ...


def _strip_code_fences(text: str) -> str:
    """Defensive cleanup for models that wrap JSON in ```json ... ``` fences."""
    cleaned = text.strip()
    cleaned = _FENCE_RE.sub("", cleaned).strip()
    return cleaned


class GeminiTextGenerationProvider:
    """Structured-JSON generation provider backed by Google Gemini."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.google_api_key
        self._model_name = model or settings.gemini_generation_model
        self._temperature = (
            temperature if temperature is not None else settings.gemini_generation_temperature
        )
        self._max_output_tokens = max_output_tokens or settings.gemini_generation_max_output_tokens
        self._client = None

    def _ensure_client(self):
        try:
            from google import genai
        except ImportError as exc:
            raise LLMGenerationError(
                "google-genai is not installed. "
                "Install it with `pip install google-genai`."
            ) from exc
        if not self._api_key:
            raise LLMGenerationError(
                "GOOGLE_API_KEY is not configured. Set it in your .env file."
            )
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def generate_json(self, prompt: str) -> dict[str, Any]:
        """Send ``prompt`` to Gemini and parse the response as a JSON object.

        Retries transient SDK/network failures with backoff; raises
        :class:`LLMGenerationError` if the model never returns valid,
        parseable JSON within the retry budget.
        """
        if not prompt or not prompt.strip():
            raise LLMGenerationError("Prompt text must not be empty.")

        client = self._ensure_client()
        from google.genai import types

        last_error: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self._temperature,
                        max_output_tokens=self._max_output_tokens,
                        response_mime_type="application/json",
                    ),
                )
                raw_text = getattr(response, "text", None)
                if raw_text is None:
                    raise LLMGenerationError("Gemini response contained no text content.")
                return self._parse_json(raw_text)
            except LLMGenerationError:
                raise
            except Exception as exc:  # noqa: BLE001 - normalize all SDK errors
                last_error = exc
                logger.warning(
                    "Gemini generation call failed (attempt %d/%d): %s",
                    attempt, _MAX_RETRIES, exc,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S * attempt)

        raise LLMGenerationError(f"Gemini generation failed after {_MAX_RETRIES} attempts: {last_error}")

    @staticmethod
    def _parse_json(raw_text: str) -> dict[str, Any]:
        cleaned = _strip_code_fences(raw_text)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMGenerationError(f"Gemini returned malformed JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMGenerationError(
                f"Gemini returned valid JSON but not a JSON object (got {type(parsed).__name__})."
            )
        return parsed
