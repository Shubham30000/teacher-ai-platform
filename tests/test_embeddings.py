from types import SimpleNamespace

import pytest

from app.core.exceptions import EmbeddingError
from app.embeddings.gemini_embeddings import GeminiEmbeddingProvider


class _FakeModelsAPI:
    """Mimics google-genai's ``client.models.embed_content`` for a fixed dimension."""

    def __init__(self, dim: int = 8, fail_times: int = 0):
        self.dim = dim
        self.fail_times = fail_times
        self.calls = 0

    def embed_content(self, model, contents, config=None):
        self.calls += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("transient failure")
        if isinstance(contents, str):
            contents = [contents]
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.1] * self.dim) for _ in contents]
        )


class _FakeGenaiClient:
    """Mimics a ``google.genai.Client`` instance."""

    def __init__(self, dim: int = 8, fail_times: int = 0):
        self.models = _FakeModelsAPI(dim=dim, fail_times=fail_times)


@pytest.fixture
def provider(monkeypatch):
    p = GeminiEmbeddingProvider(api_key="fake-key", model="gemini-embedding-001")
    fake = _FakeGenaiClient(dim=8)
    monkeypatch.setattr(p, "_ensure_client", lambda: fake)
    return p, fake


def test_embed_documents_returns_one_vector_per_text(provider):
    p, fake = provider
    vectors = p.embed_documents(["hello world", "force and pressure"])
    assert len(vectors) == 2
    assert all(len(v) == 8 for v in vectors)


def test_embed_documents_empty_list_returns_empty(provider):
    p, _ = provider
    assert p.embed_documents([]) == []


def test_embed_query_returns_single_vector(provider):
    p, _ = provider
    vector = p.embed_query("what is force")
    assert len(vector) == 8


def test_embed_documents_batches_large_input(monkeypatch):
    fake = _FakeGenaiClient(dim=4)
    p = GeminiEmbeddingProvider(api_key="fake-key", batch_size=3)
    monkeypatch.setattr(p, "_ensure_client", lambda: fake)
    texts = [f"text {i}" for i in range(7)]
    vectors = p.embed_documents(texts)
    assert len(vectors) == 7
    assert fake.models.calls == 3  # ceil(7/3)


def test_embed_retries_then_succeeds(monkeypatch):
    fake = _FakeGenaiClient(dim=4, fail_times=1)
    p = GeminiEmbeddingProvider(api_key="fake-key")
    monkeypatch.setattr(p, "_ensure_client", lambda: fake)
    monkeypatch.setattr("app.embeddings.gemini_embeddings.time.sleep", lambda *_: None)
    vectors = p.embed_documents(["hello"])
    assert len(vectors) == 1


def test_missing_api_key_raises_embedding_error():
    p = GeminiEmbeddingProvider(api_key="")
    with pytest.raises(EmbeddingError):
        p.embed_query("hello")
