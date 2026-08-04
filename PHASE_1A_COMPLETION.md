# Phase 1A Completion Report

**Project:** AI-powered Teacher Knowledge Package (TKP) platform
**Phase:** 1A — Document Ingestion & Retrieval Foundation
**Status:** Complete, per the frozen `PROJECT_ROADMAP.md` scope (no lesson generation,
teaching planner, assessments, or PDF output — those are Phase 1B+).

---

## 1. Executive Summary

Phase 1A implements the complete foundation described in `PROJECT_ROADMAP.md`:
a FastAPI backend that accepts either an uploaded document (PDF/DOCX/PPTX/TXT) or a
free-text topic request, routes it through format-specific parsers into a single
normalized `StructuredDocument` representation, chunks that document along its
educational structure (headings/sections, not arbitrary character counts), embeds
the chunks with Google's Gemini embedding model, persists them in a local ChromaDB
collection, and exposes a retriever API to query them back. No content generation
(lesson plans, assessments, activities) is implemented — that is explicitly out of
scope for this phase per the roadmap.

Every module listed in the roadmap's "PHASE 1A IMPLEMENTATION" section (items 1–13)
has a corresponding implementation below, with type hints, Pydantic models, logging,
and specific exception types throughout — no placeholders, TODOs, or pseudo-code.

**Read this section before continuing to Phase 1B — it explains what could and
could not be executed in the build environment, and why that does not indicate a
shortcut in the implementation itself.**

---

## 2. IMPORTANT: Build-Environment Execution Constraints

The sandbox this project was built in **has no network access** and does not have
`fastapi`, `pydantic`, `chromadb`, `pymupdf`, `langchain`, or `google-generativeai`
pre-installed, with no way to `pip install` them. Only `python-docx`, `python-pptx`,
`beautifulsoup4`, and `requests` were available.

This means the full `pytest` suite in `tests/` **could not be executed in this
environment** — it requires `pip install -r requirements.txt` on a machine with
network access, which is the normal, expected way to run this project.

To still validate correctness rather than submit unverified code, two things were
done:

1. **Every `.py` file was syntax-checked** with `python -m py_compile` — all pass.
2. **Core logic was smoke-tested against real inputs** using a small, local,
   throwaway duck-typed stand-in for `pydantic`/`pydantic-settings` (not shipped —
   it lived outside the project directory and is not part of this deliverable),
   combined with the real `python-docx`/`python-pptx`/`requests`/`BeautifulSoup`
   libraries that *were* available. This let the following run against real
   generated `.docx`/`.pptx` files and hand-built HTML fixtures, with actual
   assertions on the output, not inspection-only review:
   - `TxtParser`, `DocxParser`, `PptxParser` — heading/hierarchy/table/list/URL
     extraction, verified correct.
   - `TopicInterpreter` — all three example phrasings from the roadmap, plus
     casual/ambiguous phrasing and empty input, verified correct.
   - `EducationalChunker` — **this caught a real bug**: the overlap carry-over
     logic could include an oversized trailing item in full instead of respecting
     `chunk_overlap_tokens`, doubling some chunk sizes. Fixed in
     `app/chunking/chunker.py` (`_carry_overlap`) and re-verified.
   - `app/validation/validators.py` — all four validators, against valid and
     deliberately invalid documents/chunks.
   - `NcertContentResolver` — against hand-built fake HTML/HTTP responses
     (success path, no-book-found path, no-chapter-match path) — the *matching
     and downloading logic* is verified; the *live NCERT DOM selectors* are not
     (see Known Limitations).
   - `InputRouter`, `ingestion_service.run_ingestion` — full pipeline run
     end-to-end (route → chunk → embed → index) with stub embedding/vector-store
     backends, confirming job-status transitions and chunk counts.
   - `GeminiEmbeddingProvider` — batching, retry-then-succeed, and
     missing-API-key error paths, against a fake `genai` client.
   - `Retriever` — ranking, similarity-score conversion, document-id filtering,
     and empty-query error handling, against a fake vector store.

   **Not executable even with the shim**, because they require the real library
   itself, not just a pydantic stand-in: `PdfParser` (needs PyMuPDF), the FastAPI
   routes as HTTP calls (needs `fastapi`/`starlette`), `ChromaVectorStore` against
   a real Chroma collection (needs `chromadb`), and any live call to
   `https://ncert.nic.in` or the Gemini API (no network). These are written to the
   same production-quality standard and structured for direct testability
   (`tests/test_parsers_pdf.py`, `tests/test_api.py`, `tests/test_vectorstore.py`
   all exist and will run normally once installed), but were not personally
   executed by this build process.

**Action for you:** run `pip install -r requirements.txt && pytest -v` on a normal
machine before relying on this as "fully green." Everything above gives high
confidence in the logic; it is not a substitute for running the real suite once.

---

## 3. Implemented Modules (roadmap items 1–13)

| # | Roadmap item | Implementation |
|---|---|---|
| 1 | Project architecture | `app/` package layout below; `app/config.py` (pydantic-settings), `app/logging_config.py` |
| 2 | FastAPI backend | `app/main.py`, `app/api/routes/{health,upload,topic,progress}.py` |
| 3 | Input Router | `app/input_router/router.py` |
| 4 | Topic Request Interpreter | `app/topic_interpreter/{interpreter.py,models.py}` |
| 5 | Educational Content Resolver | `app/content_resolver/{ncert_resolver.py,models.py}` |
| 6 | Document Parsers | `app/parsers/{pdf_parser,docx_parser,pptx_parser,txt_parser,factory}.py` |
| 7 | Document Intelligence (StructuredDocument) | `app/document_intelligence/models.py` |
| 8 | Chunking | `app/chunking/{chunker.py,models.py}` |
| 9 | Embeddings | `app/embeddings/gemini_embeddings.py` |
| 10 | Vector Database | `app/vectorstore/chroma_store.py` |
| 11 | Retriever | `app/retriever/retriever.py` |
| 12 | Validation | `app/validation/validators.py` |
| 13 | Integration tests | `tests/` (see §6) |

Orchestration of items 3–11 into the single end-of-phase workflow lives in
`app/ingestion_service.py`, called by both `/upload` and `/topic`.

---

## 4. Repository Structure

```
teacher-ai-platform/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   ├── ingestion_service.py
│   ├── core/                  exceptions.py, constants.py
│   ├── api/routes/             health.py, upload.py, topic.py, progress.py
│   ├── input_router/           router.py
│   ├── topic_interpreter/      interpreter.py, models.py
│   ├── content_resolver/       ncert_resolver.py, models.py
│   ├── parsers/                base.py, pdf_parser.py, docx_parser.py,
│   │                            pptx_parser.py, txt_parser.py, factory.py
│   ├── document_intelligence/  models.py
│   ├── chunking/                chunker.py, models.py
│   ├── embeddings/              gemini_embeddings.py
│   ├── vectorstore/             chroma_store.py
│   ├── retriever/               retriever.py
│   ├── progress/                tracker.py
│   ├── validation/              validators.py
│   ├── models/                  schemas.py
│   └── utils/                   file_utils.py
├── tests/                       one test module per app module + test_api.py
├── data/uploads/, data/chroma_db/   (gitignored, created at runtime)
├── scripts/run_tests.sh
├── requirements.txt
├── .env.example
├── README.md
└── PHASE_1A_COMPLETION.md
```

---

## 5. Implemented APIs

- `GET /api/v1/health`
- `POST /api/v1/upload` (multipart file) → runs full ingestion, returns job id,
  document id, section/chunk counts, or a clarification message
- `POST /api/v1/topic` (`{"text": "..."}`) → interprets, resolves via NCERT if
  confident, runs full ingestion, or returns a clarification message
- `GET /api/v1/progress/{job_id}` — poll job status
- `GET /api/v1/progress/{job_id}/stream` — Server-Sent-Events version, forward
  compatible with Phase 1B's long-running generation jobs
- `POST /api/v1/retrieve` — query the vector store directly (added beyond the
  roadmap's literal endpoint list so item 11, the Retriever, is independently
  reachable/testable via HTTP, not just internal calls; does not add any
  generation surface area)

---

## 6. Implemented Parsers

All four produce the same `StructuredDocument` shape (roadmap item 7):

- **TXT** (`txt_parser.py`) — heuristic heading detection: Markdown `#`s, Setext
  underlines, numbered/"Chapter N" headings, ALL-CAPS lines; list items; URLs.
- **DOCX** (`docx_parser.py`) — walks `document.element.body` in document order
  (not `paragraphs`/`tables` separately) so interleaving is preserved; heading
  styles → hierarchy; tables; inline images saved to `<file>_assets/`; hyperlinks.
- **PPTX** (`pptx_parser.py`) — one `Section` per slide; title placeholder →
  heading; body text respects indentation level for list items; tables; picture
  shapes extracted to `<file>_assets/`; speaker notes appended, not dropped.
- **PDF** (`pdf_parser.py`, PyMuPDF) — heading level from font-size ratio to the
  document's modal body-text size (+ bold as a tie-breaker); PyMuPDF's
  `find_tables()`; images extracted via `get_images()`; pages with no extractable
  text are recorded in `metadata.extra['ocr_required_pages']` rather than silently
  dropped (see Known Limitations — OCR itself is not implemented in Phase 1A).

---

## 7. Implemented Tests

One test module per component, using real generated fixtures where possible
(`tests/conftest.py` builds actual `.docx`/`.pptx` files with `python-docx`/
`python-pptx` at test time) and fakes/stubs only for genuinely external
dependencies (Gemini API, ChromaDB in some tests, live NCERT HTTP):

`test_parsers_txt.py`, `test_parsers_docx.py`, `test_parsers_pptx.py`,
`test_parsers_pdf.py` (skips if PyMuPDF absent), `test_document_intelligence.py`,
`test_chunker.py`, `test_topic_interpreter.py`, `test_input_router.py`,
`test_content_resolver.py`, `test_embeddings.py`, `test_vectorstore.py` (skips if
chromadb absent), `test_retriever.py`, `test_validators.py`, `test_api.py` (skips
if fastapi absent).

Run with `./scripts/run_tests.sh` or `pytest -v`.

---

## 8. Completed Features

- End-to-end pipeline: upload/topic → route → parse → structure → chunk → embed →
  index, with progress tracked at every stage.
- Natural-language topic parsing with no rigid template requirement, confidence
  scoring, and graceful clarification requests.
- NCERT chapter auto-resolution with no hardcoded chapter URLs — discovery is
  driven by parsing the live index and listing pages.
- Document hierarchy (headings/subheadings, nested nesting) preserved end-to-end
  from parser → chunk (`heading_path` on every chunk).
  Tables preserved as structured cells and rendered to Markdown for embedding.
- Hierarchy-aware chunking with sentence-safe splitting for oversized paragraphs
  and token-budget-respecting overlap between chunks.
- Retrieval with cosine-similarity scoring and optional per-document filtering.
- Consistent error handling via a single `TeacherPlatformError` hierarchy, mapped
  to appropriate HTTP status codes in `app/main.py`.

---

## 9. Known Limitations

1. **NCERT resolver selectors are best-effort, not live-verified.** The build
   environment has no network access, so the CSS/DOM parsing in
   `NcertContentResolver._find_book_link` / `_parse_chapter_links` was written
   against NCERT's publicly documented page structure and defensively (multiple
   fallback strategies, generic `<select>`/`<a>` scanning rather than fixed
   selectors) but not run against the live site. Any drift only affects
   *automatic* resolution — it is fully caught by `ContentResolutionError` and
   degrades to asking the teacher to upload a reference document, per the
   roadmap's explicit requirement; it cannot crash a request. **Action:**
   smoke-test `NcertContentResolver.resolve()` against a couple of real Class/
   Subject combinations on first real run and adjust selectors if needed.
2. **No OCR.** Scanned/image-only PDF pages are detected and flagged in
   `metadata.extra['ocr_required_pages']`, not processed, per the roadmap
   ("Prepare parser routing for OCR-capable parsing later, but OCR implementation
   is NOT required in Phase 1A").
3. **Token counting is a word-count approximation**, not a real tokenizer (to
   avoid adding a heavyweight tokenizer dependency in this phase). It is
   conservative enough to stay well under the embedding model's input limit, but
   is not exact.
4. **Progress tracking is in-memory and single-process.** Fine for Phase 1A where
   ingestion completes synchronously within the request; Phase 1B's genuinely
   long-running generation jobs will need a persistent/queue-backed tracker (the
   `ProgressTracker` interface was deliberately kept swap-compatible with that).
5. **`ChromaVectorStore`/`GeminiEmbeddingProvider` were not run against the real
   services** in this build environment (see §2) — logic was verified against
   fakes; the wiring to the real SDKs follows their documented APIs but should be
   confirmed with a real `GOOGLE_API_KEY` and a real Chroma collection on first
   run.
6. **Subject inference for topic requests that omit the subject** (e.g. the
   roadmap's own "Generate teacher package for Class 10 Trigonometry" example,
   which never states a subject) correctly falls back to asking the teacher to
   clarify, rather than guessing "Mathematics" — this is a deliberate accuracy-
   over-convenience choice, flagged here in case Phase 1B wants a
   topic-to-subject inference table instead.

---

## 10. Engineering Decisions / Architecture Notes

- **Every parser returns exactly one `StructuredDocument`** (roadmap item 7) so
  chunking/embedding/retrieval never need to know which format the content came
  from — this is the single most load-bearing contract in the codebase.
- **DOCX/PPTX/PDF images and TXT tables are extracted to `<file>_assets/`
  directories next to the source file** rather than embedded in the document
  model, keeping `StructuredDocument` JSON-serializable and small; `ImageElement`
  just carries the `stored_path`.
- **Chunking walks the document hierarchy recursively**, building each chunk's
  `heading_path` from its ancestor headings — this is what will let Phase 1B's
  Teaching Planner know *where in the chapter* a retrieved fact came from, not
  just its raw text.
- **The embedding provider and vector store are injected, not hardcoded**, into
  `Retriever` and `ingestion_service.run_ingestion` — this is what made the
  fake-backed smoke testing in §2 possible, and is the same seam a future
  provider swap (different embedding model, different vector DB) would use.
- **All custom exceptions derive from one `TeacherPlatformError`** so
  `app/main.py` has a single exception handler rather than one per module.
- **The NCERT resolver never hardcodes a chapter URL** — per the roadmap's
  explicit instruction — everything is discovered by parsing the index and
  listing pages at request time.

## 11. How Phase 1A Satisfies the IIT Mandi Assignment

Phase 1A directly implements the assignment's **Stage 1: Document Intelligence**
(parsing with structure preservation) in full, and lays the retrieval
infrastructure (chunking, embeddings, vector DB, retriever with traceability via
`heading_path`/`page_number`/`source_filename` on every chunk) that Stages 2–8
will consume in Phase 1B. It intentionally does not touch Stages 2–10
(classification, knowledge extraction, planning, generation, validation,
publishing) — those are out of scope for this phase per your instructions. The
streaming-progress requirement from the assignment is implemented now
(`/progress/{job_id}` and `/progress/{job_id}/stream`) so Phase 1B's longer jobs
have somewhere to report into from day one.

---

## 12. Files Added

See §4 (Repository Structure) — every file listed there was added in this phase;
none pre-existed.

## 13. Dependencies Added

See `requirements.txt`. Notably: `fastapi`, `uvicorn`, `pydantic`/
`pydantic-settings`, `langchain`/`langchain-community`, `google-generativeai`,
`chromadb`, `pymupdf`, `python-docx`, `python-pptx`, `requests`,
`beautifulsoup4`, `playwright`, `python-dotenv`, `pytest`/`pytest-asyncio`/
`httpx`.

## 14. Execution Instructions

See `README.md` §1–2. Short version (**Python 3.10+ required**):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # then set GOOGLE_API_KEY
uvicorn app.main:app --reload
```

`requirements.txt` intentionally uses compatible version ranges rather than
exact `==` pins, since `chromadb` carries its own `fastapi`/`starlette`/
`pydantic` constraints that a hard pin here could conflict with — a plain
install in a fresh virtualenv lets pip's resolver settle on a consistent set.

## 15. Testing Instructions

```bash
pytest -v
```

## 16. Remaining Work for Phase 1B

Per the roadmap, Phase 1B begins Educational Classification (Stage 2) and
Knowledge Extraction (Stage 3) on top of this foundation:

- Build the Educational Classification stage on top of `Retriever` +
  `StructuredDocument.metadata` (Subject/Grade/Difficulty/Topic/Chapter/Category/
  Language).
- Build Knowledge Extraction (Learning Objectives, Prerequisites, Concepts,
  Definitions, Formulae, Keywords, Examples, Applications, Misconceptions) as a
  new module that consumes `Retriever` output — do not have it re-parse documents.
- Swap `ProgressTracker` to a persistent backend once generation jobs are
  genuinely long-running (minutes, not seconds).
- Smoke-test `NcertContentResolver` against the live site and adjust selectors
  per §9.1 if needed.
- Add OCR routing for `metadata.extra['ocr_required_pages']` (parser routing is
  already prepared for this per roadmap item 6; the OCR engine choice itself is
  a Phase 1B decision, not made here).
- Consider swapping the word-count token approximation in `EducationalChunker`
  for a real tokenizer if precise embedding-model input-limit compliance becomes
  necessary.

## 17. Handoff Notes for Future Claude Conversations

- **This document is the permanent implementation reference** — read it (and
  the roadmap) before touching any Phase 1A code.
- The architecture is frozen per the original instructions — Phase 1B should
  build *on top of* `StructuredDocument`/`Chunk`/`Retriever`, not replace them.
- If you're picking this up in a new sandbox: check whether `fastapi`,
  `pydantic`, `chromadb`, `pymupdf`, and `google-generativeai` are actually
  installable before assuming the previous "could not execute" constraint in §2
  still applies — if you have real network access, **run the real test suite
  first** before making changes, so you're working from ground truth instead of
  the logic-smoke-test confidence this phase relied on.
- The one confirmed bug fixed during this phase (`EducationalChunker`'s overlap
  carry-over including an oversized trailing item) is exactly the kind of thing
  that only shows up when you actually run the code against real multi-hundred-
  word content — don't skip that step for any future chunking changes either.
- `TopicInterpreter`'s subject-alias list (`_SUBJECT_ALIASES` in
  `interpreter.py`) is a reasonable NCERT Class 6–12 subject set but not
  exhaustive (e.g. regional-language subjects, vocational subjects) — extend it
  if Phase 1B sees real teacher requests it doesn't cover.
