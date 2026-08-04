from types import SimpleNamespace

import pytest

from app.core.exceptions import LLMGenerationError
from app.llm.gemini_client import GeminiTextGenerationProvider


class _FakeModelsAPI:
    def __init__(self, texts):
        self._texts = list(texts)

    def generate_content(self, model, contents, config=None):
        text = self._texts.pop(0)
        if isinstance(text, Exception):
            raise text
        return SimpleNamespace(text=text)


class _FakeGenaiClient:
    """Mimics a ``google.genai.Client`` instance."""

    def __init__(self, texts):
        self.models = _FakeModelsAPI(texts)


@pytest.fixture
def provider(monkeypatch):
    p = GeminiTextGenerationProvider(api_key="fake-key")
    return p


def test_generate_json_parses_clean_json(provider, monkeypatch):
    fake = _FakeGenaiClient(['{"subject": "Physics", "grade": 8}'])
    monkeypatch.setattr(provider, "_ensure_client", lambda: fake)
    result = provider.generate_json("classify this")
    assert result == {"subject": "Physics", "grade": 8}


def test_generate_json_strips_markdown_code_fences(provider, monkeypatch):
    fake = _FakeGenaiClient(['```json\n{"subject": "Physics"}\n```'])
    monkeypatch.setattr(provider, "_ensure_client", lambda: fake)
    result = provider.generate_json("classify this")
    assert result == {"subject": "Physics"}


def test_generate_json_retries_then_succeeds(provider, monkeypatch):
    fake = _FakeGenaiClient([RuntimeError("transient"), '{"ok": true}'])
    monkeypatch.setattr(provider, "_ensure_client", lambda: fake)
    monkeypatch.setattr("app.llm.gemini_client.time.sleep", lambda *_: None)
    result = provider.generate_json("classify this")
    assert result == {"ok": True}


def test_generate_json_raises_after_max_retries(provider, monkeypatch):
    fake = _FakeGenaiClient([RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])
    monkeypatch.setattr(provider, "_ensure_client", lambda: fake)
    monkeypatch.setattr("app.llm.gemini_client.time.sleep", lambda *_: None)
    with pytest.raises(LLMGenerationError):
        provider.generate_json("classify this")


def test_generate_json_raises_on_malformed_json(provider, monkeypatch):
    fake = _FakeGenaiClient(["not valid json {{"])
    monkeypatch.setattr(provider, "_ensure_client", lambda: fake)
    with pytest.raises(LLMGenerationError):
        provider.generate_json("classify this")


def test_generate_json_raises_on_non_object_json(provider, monkeypatch):
    fake = _FakeGenaiClient(["[1, 2, 3]"])
    monkeypatch.setattr(provider, "_ensure_client", lambda: fake)
    with pytest.raises(LLMGenerationError):
        provider.generate_json("classify this")


def test_generate_json_empty_prompt_raises():
    p = GeminiTextGenerationProvider(api_key="fake-key")
    with pytest.raises(LLMGenerationError):
        p.generate_json("   ")


def test_missing_api_key_raises_llm_generation_error():
    p = GeminiTextGenerationProvider(api_key="")
    with pytest.raises(LLMGenerationError):
        p.generate_json("hello")
