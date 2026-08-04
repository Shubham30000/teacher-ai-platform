"""
Vector Database (PROJECT_ROADMAP.md item 10).

Thin wrapper around a persistent ChromaDB collection. Embeddings are
computed upstream (by ``GeminiEmbeddingProvider``) and passed in
explicitly rather than relying on Chroma's own embedding function, so
the embedding provider stays swappable and testable in isolation.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.chunking.models import Chunk
from app.config import get_settings
from app.core.exceptions import VectorStoreError

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """Persistent local ChromaDB collection for chunk embeddings."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        persist_dir: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._collection_name = collection_name or settings.chroma_collection_name
        self._persist_dir = str(persist_dir or settings.chroma_persist_dir)
        self._client = None
        self._collection = None

    def _ensure_collection(self):
        if self._collection is not None:
            return self._collection
        try:
            import chromadb
        except ImportError as exc:
            raise VectorStoreError(
                "chromadb is not installed. Install it with `pip install chromadb`."
            ) from exc
        try:
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Failed to initialize ChromaDB collection: {exc}") from exc
        return self._collection

    def add_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise VectorStoreError(
                f"Chunk count ({len(chunks)}) does not match embedding count ({len(embeddings)})."
            )
        if not chunks:
            return
        collection = self._ensure_collection()
        try:
            collection.upsert(
                ids=[chunk.chunk_id for chunk in chunks],
                embeddings=embeddings,
                documents=[chunk.text for chunk in chunks],
                metadatas=[chunk.to_metadata_dict() for chunk in chunks],
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Failed to upsert chunks into ChromaDB: {exc}") from exc
        logger.info("Upserted %d chunks into collection '%s'", len(chunks), self._collection_name)

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[dict] = None,
    ) -> dict:
        collection = self._ensure_collection()
        try:
            return collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"ChromaDB query failed: {exc}") from exc

    def delete_document(self, document_id: str) -> None:
        collection = self._ensure_collection()
        try:
            collection.delete(where={"document_id": document_id})
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Failed to delete document {document_id}: {exc}") from exc

    def count(self) -> int:
        collection = self._ensure_collection()
        try:
            return collection.count()
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Failed to count collection: {exc}") from exc
