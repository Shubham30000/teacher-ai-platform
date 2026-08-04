import pytest

pytest.importorskip("chromadb", reason="chromadb not installed in this environment")

from app.chunking.models import Chunk  # noqa: E402
from app.vectorstore.chroma_store import ChromaVectorStore  # noqa: E402


def _chunk(doc_id: str, idx: int, text: str) -> Chunk:
    return Chunk(
        document_id=doc_id,
        section_id="sec-1",
        chunk_index=idx,
        heading_path=["1. Introduction"],
        text=text,
        approx_token_count=len(text.split()),
        page_number=1,
    )


@pytest.fixture
def store(tmp_path):
    return ChromaVectorStore(collection_name="test_collection", persist_dir=str(tmp_path))


def test_add_and_query_chunks(store):
    chunks = [_chunk("doc-1", 0, "Force is a push or pull."), _chunk("doc-1", 1, "Pressure is force per area.")]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    store.add_chunks(chunks, embeddings)
    assert store.count() == 2

    result = store.query([1.0, 0.0, 0.0], top_k=1)
    assert result["documents"][0][0] == "Force is a push or pull."


def test_add_chunks_mismatched_lengths_raises(store):
    from app.core.exceptions import VectorStoreError

    with pytest.raises(VectorStoreError):
        store.add_chunks([_chunk("doc-1", 0, "text")], [])


def test_delete_document_removes_its_chunks(store):
    chunks = [_chunk("doc-1", 0, "keep me")]
    store.add_chunks(chunks, [[0.1, 0.2, 0.3]])
    other_chunks = [_chunk("doc-2", 0, "delete me")]
    store.add_chunks(other_chunks, [[0.4, 0.5, 0.6]])
    assert store.count() == 2

    store.delete_document("doc-2")
    assert store.count() == 1
