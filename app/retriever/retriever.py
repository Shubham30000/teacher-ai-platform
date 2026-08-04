"""
Retriever (PROJECT_ROADMAP.md item 11).

Public retrieval API used by every future stage that needs grounded
context (Phase 1B's Knowledge Extraction, Teaching Planner, etc. will
all go through this, not through ChromaDB directly).
"""
from __future__ import annotations

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.exceptions import RetrievalError
from app.embeddings.gemini_embeddings import EmbeddingProvider, GeminiEmbeddingProvider
from app.vectorstore.chroma_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    heading_path: str
    document_id: str
    page_number: int
    contains_table: bool
    source_filename: str
    similarity_score: float = Field(ge=0.0, le=1.0)


class Retriever:
    """Embeds a query and returns the most relevant chunks from ChromaDB."""

    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self._vector_store = vector_store or ChromaVectorStore()
        self._embedding_provider = embedding_provider or GeminiEmbeddingProvider()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        if not query or not query.strip():
            raise RetrievalError("Query text must not be empty.")

        query_embedding = self._embedding_provider.embed_query(query)
        where = {"document_id": document_id} if document_id else None
        raw = self._vector_store.query(query_embedding, top_k=top_k, where=where)

        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        ids = (raw.get("ids") or [[]])[0] if "ids" in raw else [m.get("chunk_id", "") for m in metadatas]

        results: List[RetrievedChunk] = []
        for i, doc_text in enumerate(documents):
            metadata = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 1.0
            # Cosine distance -> similarity in [0, 1].
            similarity = max(0.0, min(1.0, 1.0 - distance))
            results.append(
                RetrievedChunk(
                    chunk_id=ids[i] if i < len(ids) else "",
                    text=doc_text,
                    heading_path=metadata.get("heading_path", ""),
                    document_id=metadata.get("document_id", ""),
                    page_number=metadata.get("page_number", -1),
                    contains_table=bool(metadata.get("contains_table", False)),
                    source_filename=metadata.get("source_filename", ""),
                    similarity_score=similarity,
                )
            )

        logger.info("Retrieved %d chunks for query %r (top_k=%d)", len(results), query, top_k)
        return results
