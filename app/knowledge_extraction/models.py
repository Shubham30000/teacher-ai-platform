"""
Knowledge Extraction data contract (Phase 1B, PROJECT_ROADMAP.md
section 14.1).

``KnowledgeJSON`` is the structured educational representation produced
from a ``StructuredDocument`` + its ``DocumentMetadata``. It is the
grounding source for every Phase 2 stage (Teaching Planner, Content/
Activity/Assessment Generators, Validation).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class BloomLevel(str, Enum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class RelationshipType(str, Enum):
    PREREQUISITE_OF = "prerequisite_of"
    PART_OF = "part_of"
    RELATED_TO = "related_to"
    LEADS_TO = "leads_to"


class LearningObjective(BaseModel):
    id: str = Field(default_factory=lambda: f"obj-{uuid4().hex[:8]}")
    text: str
    bloom_level: Optional[BloomLevel] = None


class Prerequisite(BaseModel):
    id: str = Field(default_factory=lambda: f"pre-{uuid4().hex[:8]}")
    concept: str
    description: str = ""


class Concept(BaseModel):
    id: str = Field(default_factory=lambda: f"concept-{uuid4().hex[:8]}")
    name: str
    description: str = ""
    related_concept_ids: List[str] = Field(default_factory=list)


class Definition(BaseModel):
    id: str = Field(default_factory=lambda: f"def-{uuid4().hex[:8]}")
    term: str
    definition: str
    concept_id: Optional[str] = None


class Formula(BaseModel):
    id: str = Field(default_factory=lambda: f"formula-{uuid4().hex[:8]}")
    name: str
    expression: str
    description: str = ""
    variables: Dict[str, str] = Field(default_factory=dict)


class Example(BaseModel):
    id: str = Field(default_factory=lambda: f"example-{uuid4().hex[:8]}")
    description: str
    concept_id: Optional[str] = None


class Application(BaseModel):
    id: str = Field(default_factory=lambda: f"app-{uuid4().hex[:8]}")
    description: str
    real_world_context: str = ""


class Misconception(BaseModel):
    id: str = Field(default_factory=lambda: f"misc-{uuid4().hex[:8]}")
    statement: str
    correction: str
    related_concept_id: Optional[str] = None


class ConceptRelationship(BaseModel):
    source_concept_id: str
    target_concept_id: str
    relationship_type: RelationshipType


class KnowledgeJSON(BaseModel):
    """Structured educational representation of a document.

    Produced by :class:`app.knowledge_extraction.extractor.KnowledgeExtractor`.
    ``grounding_chunk_ids`` records which retrieved chunks were used as
    context for extraction, supporting the assignment's RAG traceability
    bonus criterion.
    """

    document_id: str
    learning_objectives: List[LearningObjective] = Field(default_factory=list)
    prerequisites: List[Prerequisite] = Field(default_factory=list)
    concepts: List[Concept] = Field(default_factory=list)
    definitions: List[Definition] = Field(default_factory=list)
    formulae: List[Formula] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    examples: List[Example] = Field(default_factory=list)
    applications: List[Application] = Field(default_factory=list)
    misconceptions: List[Misconception] = Field(default_factory=list)
    relationships: List[ConceptRelationship] = Field(default_factory=list)
    grounding_chunk_ids: List[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
