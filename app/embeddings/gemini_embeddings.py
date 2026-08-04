"""
Embeddings (PROJECT_ROADMAP.md item 9).

Wraps Google's Gemini embedding model (``gemini-embedding-001`` by
default, configurable) via the ``google-genai`` SDK. Kept as a
thin, swappable provider class (``GeminiEmbeddingProvider``) behind a
small interface so the vector store / retriever never talk to the
Gemini SDK directly - only to this module.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Protocol

from app.config import get_settings
from app.core.exceptions import EmbeddingError

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 1.5


class EmbeddingProvider(Protocol):
    """Interface any embedding backend must satisfy."""

    def embed_documents(self, texts: List[str]) -> List[List[float]]: ...

    def embed_query(self, text: str) -> List[float]: ...

    @property
    def dimensions(self) -> int: ...


class GeminiEmbeddingProvider:
    """Embedding provider backed by Google Gemini's embedding endpoint."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = 16,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.google_api_key
        self._model = model or settings.gemini_embedding_model
        self._dimensions = settings.gemini_embedding_dimensions
        self._batch_size = batch_size
        self._client = None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _ensure_client(self):
        try:
            from google import genai
        except ImportError as exc:
            raise EmbeddingError(
                "google-genai is not installed. "
                "Install it with `pip install google-genai`."
            ) from exc
        if not self._api_key:
            raise EmbeddingError(
                "GOOGLE_API_KEY is not configured. Set it in your .env file."
            )
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = self._ensure_client()
        settings = get_settings()
        embeddings: List[List[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            embeddings.extend(
                self._embed_batch(client, batch, task_type=settings.gemini_embedding_task_type)
            )
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        client = self._ensure_client()
        result = self._embed_batch(client, [text], task_type="RETRIEVAL_QUERY")
        return result[0]

    def _embed_batch(self, client, batch: List[str], task_type: str) -> List[List[float]]:
        from google.genai import types

        last_error: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = client.models.embed_content(
                    model=self._model,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self._dimensions,
                    ),
                )
                # The SDK returns an EmbedContentResponse with an
                # ``embeddings`` list of ContentEmbedding objects (each
                # exposing ``.values``). Support a plain-dict shape too,
                # since fakes/tests may model the response either way.
                raw_embeddings = getattr(response, "embeddings", None)
                if raw_embeddings is None and isinstance(response, dict):
                    raw_embeddings = response.get("embeddings")
                if not raw_embeddings:
                    raise EmbeddingError("Gemini embedding response contained no embeddings.")
                vectors = [
                    list(item.values) if hasattr(item, "values") else list(item["values"])
                    for item in raw_embeddings
                ]
                return vectors
            except Exception as exc:  # noqa: BLE001 - normalize all SDK errors
                last_error = exc
                logger.warning(
                    "Gemini embedding call failed (attempt %d/%d): %s",
                    attempt, _MAX_RETRIES, exc,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S * attempt)
        raise EmbeddingError(f"Gemini embedding failed after {_MAX_RETRIES} attempts: {last_error}")
