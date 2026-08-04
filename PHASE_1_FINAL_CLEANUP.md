# PHASE 1 — Final Cleanup & Roadmap Synchronization

**Status:** Complete
**Scope:** Cleanup and documentation synchronization only. No Phase 2 work, no new
features, no architecture redesign was performed as part of this pass.

---

## 1. Summary of Removed Functionality

The automatic **NCERT retrieval workflow** (originally called the *Educational
Content Resolver* in earlier design docs) has been permanently removed from the
codebase. That workflow was:

```
Teacher enters text
        ↓
Topic Interpreter
        ↓
Automatically connect to the NCERT website
        ↓
Resolve Grade → Resolve Subject → Resolve Book → Resolve Chapter
        ↓
Automatically download the chapter PDF
        ↓
Feed it into the ingestion pipeline
```

This entire automatic-retrieval path (website connection, grade/subject/book/
chapter resolution, and automatic PDF download) has been deleted. It was never
exposed through a public API in a way that changes behavior for API consumers
of Mode 1 (file upload) — the removal is isolated to Mode 2 (Topic Mode).

## 2. Reason for Removal

This was an intentional, permanent product decision, not a bug fix or a
temporary rollback:

- The NCERT website does not expose chapter titles in its HTML — links are
  only labeled "Chapter 1", "Chapter 2", etc.
- Reliable topic-to-chapter matching would have required downloading every
  chapter PDF up front just to determine which one was correct.
- Subject-to-grade mappings are inconsistent across grades (e.g. "History"
  becomes "Social Science" at some grade levels), making a general resolver
  brittle.
- Browser automation (Playwright) and HTML scraping (requests + BeautifulSoup)
  added ongoing maintenance surface (site layout changes, headless-browser
  lifecycle management, retry logic) disproportionate to the value delivered.
- The project's focus is document intelligence and educational AI, not web
  crawling/scraping infrastructure.
- The added complexity was not justified for the project's scope.

## 3. Current Topic Mode Architecture

Topic Mode is now **NLP interpretation only**. Given free text such as:

> Class 8 Science Force and Pressure

the `TopicInterpreter` extracts:

- Grade
- Subject
- Topic
- Confidence score (plus a list of any missing fields)

Topic Mode never performs web scraping, browser automation, PDF downloads,
NCERT crawling, or any other automatic external retrieval. Regardless of how
confident the extraction is, if no document has been uploaded yet the system
returns a structured response (`needs_clarification: true`) explaining that an
uploaded educational document is required before a teaching package can be
generated. Once a document is uploaded, Topic Mode and Upload Mode converge on
the identical downstream ingestion pipeline.

## 4. Repository Cleanup Summary

**Removed entirely:**
- `app/content_resolver/` (the whole module: `ncert_resolver.py`, `models.py`,
  and its `__init__.py`)
- `tests/test_content_resolver.py`

**Edited to remove NCERT-only code paths:**
- `app/input_router/router.py` — dropped the `content_resolver` dependency and
  `ResolvedContent` handling; `_route_topic_mode` now only calls the
  `TopicInterpreter` and always returns a clarification/upload-request result.
- `app/core/exceptions.py` — removed `ContentResolutionError` (only raised by
  the deleted resolver).
- `app/core/constants.py` — removed the `RESOLVING_CONTENT` pipeline stage.
- `app/progress/tracker.py` — removed the `RESOLVING_CONTENT` entry from the
  stage-progress map.
- `app/config.py` — removed `ncert_base_url`, `ncert_request_timeout_s`, and
  `ncert_max_retries` settings.
- `.env` — removed the corresponding `NCERT_*` environment variables.
- `app/validation/validators.py` — reworded a comment that referenced
  "non-NCERT reference material" to generic language, since automatic NCERT
  retrieval is no longer part of the system's vocabulary.
- `tests/test_input_router.py` — removed the `_StubResolver`/`ResolvedContent`
  test double and its test case; added a test confirming that even a
  confident Topic Mode extraction still asks the teacher to upload a document
  (it never auto-resolves one).

**Left unchanged (verified as unrelated to the removed feature):**
- `tests/conftest.py` and `tests/test_parsers_txt.py` reference an
  `ncert.nic.in` URL only as example text used to test the TXT parser's
  generic URL-extraction logic — this is not part of the abandoned retrieval
  feature and was left in place.
- `app/config.py`'s remaining settings, `app/topic_interpreter/*`, and
  `app/api/routes/topic.py` were already NLP-only / resolver-agnostic and
  needed no changes.

## 5. Dependencies Removed

Removed from `requirements.txt` (used exclusively by the deleted resolver):

- `requests`
- `beautifulsoup4`
- `playwright`

No other module in the repository imports any of these three packages.

## 6. Updated Phase 1 Architecture

```
Upload / Topic request
        ↓
   Input Router
        ↓
Parser (PDF/DOCX/PPTX/TXT)          [Topic Mode: interpret text only, then
        ↓                            ask teacher to upload a document]
  StructuredDocument
        ↓
 Educational Chunker
        ↓
 Gemini Embeddings
        ↓
     ChromaDB
        ↓
    Retriever
        ↓
 Educational Classification  →  DocumentMetadata
        ↓
  Knowledge Extraction        →  KnowledgeJSON
```

Topic Mode workflow specifically:

```
Teacher Input
    ↓
Topic Interpretation
    ↓
Metadata Extraction (grade / subject / topic / confidence)
    ↓
Waiting for Uploaded Document
    ↓
Existing Ingestion Pipeline
```

## 7. Confirmation of Synchronization

`PROJECT_ROADMAP.md` has been amended in place (see the recorded amendment
note in §4 "Mode 2 — Topic Mode") and its architecture diagrams, module
dependency diagram, folder structure, data-flow description, pipeline I/O
contract table, error-handling strategy, environment-variable table, and
Phase 1 scope/modules/deliverables/Definition-of-Done/risks have all been
updated to remove references to automatic NCERT retrieval, browser
automation, Playwright, website scraping, automatic chapter download, and
NCERT indexing, and to describe the simplified NLP-only Topic Mode instead.
The roadmap and the implemented repository are synchronized as of this
cleanup.

## 8. Validation Performed

- ✅ All Python files in `app/` and `tests/` compile cleanly
  (`python -m py_compile`) — no syntax errors introduced by the removal.
- ✅ No remaining imports of, or references to, `content_resolver`,
  `NcertContentResolver`, `ResolvedContent`, `ContentResolutionError`,
  `RESOLVING_CONTENT`, or any `ncert_*` config/env var anywhere in `app/` or
  `tests/` (verified by repository-wide search).
- ✅ No remaining imports of `requests`, `bs4`/`beautifulsoup4`, or
  `playwright` anywhere in the codebase.
- ✅ Upload Mode (`app/input_router/router.py::_route_file_upload`) is
  unchanged and still delegates to `ParserFactory`.
- ✅ Topic Interpreter (`app/topic_interpreter/`) is unchanged — it already
  performed NLP-only extraction and never depended on the resolver.
- ✅ `app/ingestion_service.py` is unchanged; it already only consumed
  `RoutingResult.structured_document` / `needs_clarification`, neither of
  which referenced the resolver.
- ⚠️ Full `pytest` execution could not be run in this environment (no network
  access to install `requirements.txt`), so compilation and manual
  cross-reference checks were used in its place. The test suite itself
  (`tests/test_input_router.py`) has been updated to match the new behavior
  and should be run in a networked environment before merging.
