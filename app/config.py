"""
Centralized application configuration.

All environment-dependent values are read here, exactly once, via
pydantic-settings. Nothing else in the codebase should call
``os.environ`` directly - import ``get_settings()`` instead so that
configuration stays single-sourced and testable (tests can override
env vars before ``get_settings`` is first called, or monkeypatch the
cached instance).
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration, populated from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "Teacher AI Platform"
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)

    # --- API ---
    api_v1_prefix: str = "/api/v1"
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    # --- Storage paths ---
    upload_dir: Path = Field(default=BASE_DIR / "data" / "uploads")
    chroma_persist_dir: Path = Field(default=BASE_DIR / "data" / "chroma_db")
    outputs_dir: Path = Field(default=BASE_DIR / "data" / "outputs")

    # --- Upload constraints ---
    max_upload_size_mb: int = Field(default=50)
    allowed_extensions: List[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".pptx", ".txt"]
    )

    # --- Google Gemini ---
    google_api_key: str = Field(default="")
    gemini_embedding_model: str = Field(default="gemini-embedding-001")
    gemini_embedding_task_type: str = Field(default="RETRIEVAL_DOCUMENT")
    gemini_embedding_dimensions: int = Field(default=768)

    # --- ChromaDB ---
    chroma_collection_name: str = Field(default="teacher_knowledge_chunks")

    # --- Chunking ---
    chunk_max_tokens: int = Field(default=450)
    chunk_overlap_tokens: int = Field(default=60)
    chunk_min_tokens: int = Field(default=40)

    # --- Gemini text generation (Educational Classification / Knowledge Extraction) ---
    gemini_generation_model: str = Field(default="gemini-2.5-flash")
    gemini_generation_temperature: float = Field(default=0.2)
    gemini_generation_max_output_tokens: int = Field(default=8192)

    # --- Prompt templates ---
    prompts_dir: Path = Field(default=BASE_DIR / "prompts")

    # --- Educational Classification ---
    classification_retrieval_top_k: int = Field(default=6)
    classification_context_char_limit: int = Field(default=6000)

    # --- Knowledge Extraction ---
    knowledge_extraction_retrieval_top_k: int = Field(default=14)
    knowledge_extraction_context_char_limit: int = Field(default=14000)

    # --- Teaching Package (Phase 2A) ---
    teaching_package_generation_temperature: float = Field(default=0.4)

    def ensure_directories(self) -> None:
        """Create storage directories if they do not already exist."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings
