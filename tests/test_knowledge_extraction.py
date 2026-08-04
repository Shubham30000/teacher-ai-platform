import pytest

from app.classification.models import ContentCategory, DifficultyLevel
from app.classification.models import DocumentMetadata as ClassificationMetadata
from app.core.exceptions import KnowledgeExtractionError, LLMGenerationError
from app.document_intelligence.models import (
    ContentBlock,
    DocumentMetadata as FileMetadata,
    HeadingLevel,
    Section,
    StructuredDocument,
)
from app.knowledge_extraction.extractor import KnowledgeExtractor
from app.retriever.retriever import RetrievedChunk


def _sample_document() -> StructuredDocument:
    section = Section(heading="8. Force and Pressure", heading_level=HeadingLevel.H1)
    section.blocks.append(ContentBlock(text="Push or pull is called force."))
    sub = Section(heading="8.2 Pressure", heading_level=HeadingLevel.H2)
    sub.blocks.append(ContentBlock(text="Pressure is the force acting per unit area."))
    section.subsections.append(sub)
    return StructuredDocument(
        metadata=FileMetadata(source_filename="chapter.pdf", file_type="pdf"),
        sections=[section],
    )


def _sample_metadata(document_id: str) -> ClassificationMetadata:
    return ClassificationMetadata(
        document_id=document_id,
        subject="Physics",
        grade=8,
        topic="Force and Pressure",
        chapter="Chapter 8",
        language="English",
        difficulty=DifficultyLevel.BEGINNER,
        category=ContentCategory.CONCEPTUAL,
        confidence=0.9,
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
        "learning_objectives": [{"id": "obj-1", "text": "Define force.", "bloom_level": "understand"}],
        "prerequisites": [],
        "concepts": [
            {"id": "concept-force", "name": "Force", "description": "A push or pull.",
             "related_concept_ids": ["concept-pressure"]},
            {"id": "concept-pressure", "name": "Pressure", "description": "Force per unit area.",
             "related_concept_ids": []},
        ],
        "definitions": [
            {"id": "def-1", "term": "Force", "definition": "A push or pull.",
             "concept_id": "concept-force"}
        ],
        "formulae": [
            {"id": "formula-1", "name": "Pressure", "expression": "P = F / A",
             "description": "Pressure formula", "variables": {"P": "pressure", "F": "force", "A": "area"}}
        ],
        "keywords": ["force", "pressure"],
        "examples": [{"id": "example-1", "description": "Pushing a door.", "concept_id": "concept-force"}],
        "applications": [{"id": "app-1", "description": "Hydraulic brakes.", "real_world_context": "Cars"}],
        "misconceptions": [
            {"id": "misc-1", "statement": "Force and pressure are the same.",
             "correction": "They are related but distinct.", "related_concept_id": "concept-force"}
        ],
        "relationships": [
            {"source_concept_id": "concept-force", "target_concept_id": "concept-pressure",
             "relationship_type": "related_to"}
        ],
    }
    base.update(overrides)
    return base


def test_extract_returns_valid_knowledge_json():
    document = _sample_document()
    llm = _FakeLLM(response=_valid_response())
    extractor = KnowledgeExtractor(llm_provider=llm)

    knowledge = extractor.extract(document, _sample_metadata(document.document_id))

    assert knowledge.document_id == document.document_id
    assert len(knowledge.concepts) == 2
    assert len(knowledge.learning_objectives) == 1
    assert knowledge.formulae[0].expression == "P = F / A"
    assert knowledge.relationships[0].relationship_type.value == "related_to"


def test_extract_prompt_includes_classification_metadata():
    document = _sample_document()
    llm = _FakeLLM(response=_valid_response())
    extractor = KnowledgeExtractor(llm_provider=llm)

    extractor.extract(document, _sample_metadata(document.document_id))

    assert "Physics" in llm.last_prompt
    assert "Force and Pressure" in llm.last_prompt


def test_extract_uses_retriever_and_records_grounding_chunk_ids():
    document = _sample_document()
    chunks = [
        RetrievedChunk(
            chunk_id="c1", text="Pressure is force per unit area.", heading_path="8.2 Pressure",
            document_id=document.document_id, page_number=2, contains_table=False,
            source_filename="chapter.pdf", similarity_score=0.88,
        ),
        RetrievedChunk(
            chunk_id="c2", text="Force is a push or pull.", heading_path="8. Force and Pressure",
            document_id=document.document_id, page_number=1, contains_table=False,
            source_filename="chapter.pdf", similarity_score=0.95,
        ),
    ]
    retriever = _FakeRetriever(chunks)
    llm = _FakeLLM(response=_valid_response())
    extractor = KnowledgeExtractor(llm_provider=llm, retriever=retriever)

    knowledge = extractor.extract(document, _sample_metadata(document.document_id))

    assert retriever.last_call["document_id"] == document.document_id
    assert knowledge.grounding_chunk_ids == ["c1", "c2"]
    assert "Pressure is force per unit area." in llm.last_prompt


def test_extract_falls_back_to_full_text_without_retriever():
    document = _sample_document()
    llm = _FakeLLM(response=_valid_response())
    extractor = KnowledgeExtractor(llm_provider=llm)

    knowledge = extractor.extract(document, _sample_metadata(document.document_id))

    assert knowledge.grounding_chunk_ids == []
    assert "Push or pull is called force." in llm.last_prompt


def test_extract_raises_knowledge_extraction_error_on_llm_failure():
    document = _sample_document()
    llm = _FakeLLM(error=LLMGenerationError("boom"))
    extractor = KnowledgeExtractor(llm_provider=llm)
    with pytest.raises(KnowledgeExtractionError):
        extractor.extract(document, _sample_metadata(document.document_id))


def test_extract_raises_on_malformed_relationship_type():
    document = _sample_document()
    llm = _FakeLLM(response=_valid_response(
        relationships=[{"source_concept_id": "concept-force", "target_concept_id": "concept-pressure",
                         "relationship_type": "not-a-real-type"}]
    ))
    extractor = KnowledgeExtractor(llm_provider=llm)
    with pytest.raises(KnowledgeExtractionError):
        extractor.extract(document, _sample_metadata(document.document_id))


def test_extract_allows_empty_formulae_for_non_quantitative_content():
    document = _sample_document()
    llm = _FakeLLM(response=_valid_response(formulae=[]))
    extractor = KnowledgeExtractor(llm_provider=llm)
    knowledge = extractor.extract(document, _sample_metadata(document.document_id))
    assert knowledge.formulae == []
