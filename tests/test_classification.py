import pytest

from app.classification.classifier import EducationalClassifier
from app.classification.models import ContentCategory, DifficultyLevel
from app.core.exceptions import ClassificationError, LLMGenerationError
from app.document_intelligence.models import (
    ContentBlock,
    DocumentMetadata as FileMetadata,
    HeadingLevel,
    Section,
    StructuredDocument,
)
from app.retriever.retriever import RetrievedChunk


def _sample_document() -> StructuredDocument:
    section = Section(heading="8. Force and Pressure", heading_level=HeadingLevel.H1)
    section.blocks.append(ContentBlock(text="Push or pull is called force."))
    sub = Section(heading="8.2 Pressure", heading_level=HeadingLevel.H2)
    sub.blocks.append(ContentBlock(text="Pressure is force per unit area."))
    section.subsections.append(sub)
    return StructuredDocument(
        metadata=FileMetadata(source_filename="chapter.pdf", file_type="pdf"),
        sections=[section],
    )


class _FakeLLM:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.last_prompt = None

    def generate_json(self, prompt):
        self.last_prompt = prompt
        if self._error:
            raise self._error
        return self._response


class _FakeRetriever:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_call = None

    def retrieve(self, query, top_k=5, document_id=None):
        self.last_call = {"query": query, "top_k": top_k, "document_id": document_id}
        return self._chunks


def _valid_response(**overrides):
    base = {
        "subject": "Physics",
        "grade": 8,
        "topic": "Force and Pressure",
        "chapter": "Chapter 8",
        "language": "English",
        "difficulty": "beginner",
        "category": "conceptual",
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def test_classify_returns_valid_document_metadata():
    llm = _FakeLLM(response=_valid_response())
    classifier = EducationalClassifier(llm_provider=llm)
    metadata = classifier.classify(_sample_document())

    assert metadata.subject == "Physics"
    assert metadata.grade == 8
    assert metadata.difficulty == DifficultyLevel.BEGINNER
    assert metadata.category == ContentCategory.CONCEPTUAL
    assert metadata.confidence == pytest.approx(0.9)


def test_classify_prompt_includes_heading_outline_and_filename():
    llm = _FakeLLM(response=_valid_response())
    classifier = EducationalClassifier(llm_provider=llm)
    classifier.classify(_sample_document())

    assert "chapter.pdf" in llm.last_prompt
    assert "Force and Pressure" in llm.last_prompt


def test_classify_uses_retriever_when_available():
    chunks = [
        RetrievedChunk(
            chunk_id="c1", text="Force is a push or pull.", heading_path="8. Force and Pressure",
            document_id="doc-1", page_number=1, contains_table=False,
            source_filename="chapter.pdf", similarity_score=0.9,
        )
    ]
    retriever = _FakeRetriever(chunks)
    llm = _FakeLLM(response=_valid_response())
    classifier = EducationalClassifier(llm_provider=llm, retriever=retriever)

    document = _sample_document()
    classifier.classify(document)

    assert retriever.last_call["document_id"] == document.document_id
    assert "Force is a push or pull." in llm.last_prompt


def test_classify_falls_back_to_full_text_when_retriever_returns_nothing():
    retriever = _FakeRetriever(chunks=[])
    llm = _FakeLLM(response=_valid_response())
    classifier = EducationalClassifier(llm_provider=llm, retriever=retriever)

    document = _sample_document()
    classifier.classify(document)

    assert "Pressure is force per unit area." in llm.last_prompt


def test_classify_raises_classification_error_on_llm_failure():
    llm = _FakeLLM(error=LLMGenerationError("boom"))
    classifier = EducationalClassifier(llm_provider=llm)
    with pytest.raises(ClassificationError):
        classifier.classify(_sample_document())


def test_classify_raises_classification_error_on_invalid_difficulty():
    llm = _FakeLLM(response=_valid_response(difficulty="super-hard"))
    classifier = EducationalClassifier(llm_provider=llm)
    with pytest.raises(ClassificationError):
        classifier.classify(_sample_document())


def test_classify_allows_null_grade_and_chapter():
    llm = _FakeLLM(response=_valid_response(grade=None, chapter=None))
    classifier = EducationalClassifier(llm_provider=llm)
    metadata = classifier.classify(_sample_document())
    assert metadata.grade is None
    assert metadata.chapter is None
