"""Custom exception hierarchy for the Teacher AI Platform.

Using specific exception types (rather than bare ``Exception``) lets the
FastAPI exception handlers in ``app.main`` return meaningful, consistent
HTTP error responses, and lets calling code catch precisely what it
expects instead of swallowing unrelated errors.
"""


class TeacherPlatformError(Exception):
    """Base class for all application-specific errors."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedFileTypeError(TeacherPlatformError):
    """Raised when an uploaded file's extension/mimetype is not supported."""


class FileTooLargeError(TeacherPlatformError):
    """Raised when an uploaded file exceeds the configured size limit."""


class ParsingError(TeacherPlatformError):
    """Raised when a document parser fails to extract content from a file."""


class ChunkingError(TeacherPlatformError):
    """Raised when chunking a StructuredDocument fails."""


class EmbeddingError(TeacherPlatformError):
    """Raised when the embedding provider fails or returns malformed output."""


class VectorStoreError(TeacherPlatformError):
    """Raised for ChromaDB read/write failures."""


class RetrievalError(TeacherPlatformError):
    """Raised when the retriever fails to complete a query."""


class JobNotFoundError(TeacherPlatformError):
    """Raised when a progress/job id is not recognized."""


class PromptLoadError(TeacherPlatformError):
    """Raised when a prompt template cannot be loaded or is missing required placeholders."""


class LLMGenerationError(TeacherPlatformError):
    """Raised when a Gemini text-generation call fails or returns malformed JSON."""


class ClassificationError(TeacherPlatformError):
    """Raised when Educational Classification cannot produce valid DocumentMetadata."""


class KnowledgeExtractionError(TeacherPlatformError):
    """Raised when Knowledge Extraction cannot produce a valid KnowledgeJSON."""


class TeachingPackageGenerationError(TeacherPlatformError):
    """Raised when a single Teaching Package module (Phase 2A) fails to generate."""


class TeachingPackageNotFoundError(TeacherPlatformError):
    """Raised when no persisted TeachingPackage exists for a given document_id."""
