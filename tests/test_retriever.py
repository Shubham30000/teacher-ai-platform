import pytest

from app.core.exceptions import RetrievalError
from app.retriever.retriever import Retriever


class _FakeEmbeddingProvider:
    dimensions = 3

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]

    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class _FakeVectorStore:
    def __init__(self, response):
        self._response = response
        self.last_query = None

    def query(self, query_embedding, top_k=5, where=None):
        self.last_query = {"embedding": query_embedding, "top_k": top_k, "where": where}
        return self._response


def _canned_response():
    return {
        "ids": [["chunk-1", "chunk-2"]],
        "documents": [["Force is a push or pull.", "Pressure is force per area."]],
        "metadatas": [
            [
                {
                    "document_id": "doc-1",
                    "heading_path": "1. Introduction",
                    "page_number": 1,
                    "contains_table": False,
                    "source_filename": "chapter.pdf",
                },
                {
                    "document_id": "doc-1",
                    "heading_path": "1.2 Pressure",
                    "page_number": 3,
                    "contains_table": True,
                    "source_filename": "chapter.pdf",
                },
            ]
        ],
        "distances": [[0.05, 0.4]],
    }


def test_retrieve_returns_ranked_chunks():
    store = _FakeVectorStore(_canned_response())
    retriever = Retriever(vector_store=store, embedding_provider=_FakeEmbeddingProvider())
    results = retriever.retrieve("what is force", top_k=2)
    assert len(results) == 2
    assert results[0].chunk_id == "chunk-1"
    assert results[0].similarity_score == pytest.approx(0.95)
    assert results[1].contains_table is True


def test_retrieve_passes_document_id_filter():
    store = _FakeVectorStore(_canned_response())
    retriever = Retriever(vector_store=store, embedding_provider=_FakeEmbeddingProvider())
    retriever.retrieve("what is force", top_k=2, document_id="doc-1")
    assert store.last_query["where"] == {"document_id": "doc-1"}


def test_retrieve_empty_query_raises():
    store = _FakeVectorStore(_canned_response())
    retriever = Retriever(vector_store=store, embedding_provider=_FakeEmbeddingProvider())
    with pytest.raises(RetrievalError):
        retriever.retrieve("   ")


def test_retrieve_handles_no_results():
    store = _FakeVectorStore({"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]})
    retriever = Retriever(vector_store=store, embedding_provider=_FakeEmbeddingProvider())
    results = retriever.retrieve("anything")
    assert results == []
