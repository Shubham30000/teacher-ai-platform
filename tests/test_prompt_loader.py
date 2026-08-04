import pytest

from app.core.exceptions import PromptLoadError
from app.prompt_engine.loader import clear_prompt_cache, load_prompt_template, render_prompt


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_prompt_cache()
    yield
    clear_prompt_cache()


def test_load_prompt_template_reads_classification_prompt():
    text = load_prompt_template("classification_prompt.md")
    assert "SYSTEM" in text
    assert "{{SOURCE_FILENAME}}" in text


def test_load_prompt_template_reads_knowledge_extraction_prompt():
    text = load_prompt_template("knowledge_extraction_prompt.md")
    assert "learning_objectives" in text
    assert "{{DOCUMENT_CONTEXT}}" in text


def test_load_prompt_template_missing_file_raises():
    with pytest.raises(PromptLoadError):
        load_prompt_template("does_not_exist.md")


def test_render_prompt_substitutes_all_placeholders():
    rendered = render_prompt(
        "classification_prompt.md",
        {
            "SOURCE_FILENAME": "chapter.pdf",
            "HEADING_OUTLINE": "- Chapter 8",
            "DOCUMENT_CONTEXT": "Force is a push or pull.",
        },
    )
    assert "{{" not in rendered
    assert "chapter.pdf" in rendered
    assert "Force is a push or pull." in rendered


def test_render_prompt_missing_variable_raises():
    with pytest.raises(PromptLoadError):
        render_prompt("classification_prompt.md", {"SOURCE_FILENAME": "chapter.pdf"})


def test_render_prompt_does_not_collide_with_literal_json_braces():
    """The output-format section of the templates contains literal JSON
    braces; render_prompt must not choke on those or try to substitute them."""
    rendered = render_prompt(
        "knowledge_extraction_prompt.md",
        {
            "SUBJECT": "Physics",
            "GRADE": "8",
            "TOPIC": "Force",
            "CHAPTER": "Ch. 8",
            "DIFFICULTY": "beginner",
            "DOCUMENT_CONTEXT": "Force is a push or pull.",
        },
    )
    assert '"learning_objectives"' in rendered
