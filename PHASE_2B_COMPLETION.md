# Phase 2B Summary

## Objectives

Build a browser-based interface on top of the existing, working Phase
1/2A backend (parsing → classification → knowledge extraction → Teaching
Package generation) without redesigning or refactoring that backend's AI
pipeline. Scope: Home, Upload, Progress, Results, Error, and 404 pages;
real progress tracking; and JSON/PDF/DOCX downloads.

## Features Implemented

### Browser UI
Six server-rendered pages (Home, Upload, Progress, Results, Error, 404),
plain CSS, and vanilla JavaScript. No frontend framework.

### Upload Workflow
The Upload page validates the file client-side (extension, non-empty,
size limit) before submitting, then submits via `fetch` to
`/api/v1/upload`.

### Real Progress Tracking
`/api/v1/upload` returns immediately with a `job_id`; the pipeline
(ingestion + Teaching Package generation) runs in a FastAPI
`BackgroundTask`. The Upload/Progress view polls
`GET /api/v1/progress/{job_id}` on an interval and renders the real
stage name and the real percentage from `app/progress/tracker.py`'s
`_STAGE_PROGRESS` map — nothing is simulated. A new `generating_package`
`JobStage` was added so the Teaching Package generation step (which
previously had no stage of its own) is now visible in the same real
progress stream. On completion, the poll response carries the full
result (document id, metadata, knowledge summary, teaching package
summary), and the page redirects to Results.

### Results Page
Shows filename, document metadata (subject/grade/topic/chapter/
difficulty), a knowledge summary (counts per category), a teaching
package summary, and each of the nine generated modules in a
collapsible card. Data comes from `GET /api/v1/export/{document_id}/json`
(the same endpoint the JSON download button uses).

### Download JSON / PDF / DOCX
Three buttons on the Results page, each a plain link to one of the new
`/api/v1/export/{document_id}/{json,pdf,docx}` endpoints.

### Error Handling
A single Error page renders a friendly title, message, and suggested
action for any failure category (unsupported file, oversized file,
parsing failure, embedding/classification/knowledge-extraction/teaching-
package-generation failure, network error, timeout, generic server
error). No stack traces or raw exception text are ever shown to the
user.

### Frontend Architecture
Jinja2 templates (`templates/`) rendered by `app/web/routes.py`, plain
CSS (`static/css/style.css`), and five small vanilla-JS modules
(`static/js/app.js`, `upload.js`, `progress.js`, `results.js`,
`error.js`) — one per page's behavior, plus `app.js` for shared helpers
(file validation, the stage list, error-message mapping,
`sessionStorage` helpers).

### Backend Architecture
Two small, additive backend changes made real progress tracking
possible (see Engineering Decisions below): `/api/v1/upload` now
schedules the pipeline via `BackgroundTasks` instead of running it
inline, and a `JobStage.GENERATING_PACKAGE` stage plus a `result` field
on `ProgressResponse` were added so the poller can see the Teaching
Package generation step and read the final result. No parsing,
chunking, embedding, classification, knowledge extraction, prompt, or
generation logic was changed.

### Export Architecture
`app/utils/export_utils.py` builds one shared list of `(heading, lines)`
sections from the already-persisted bundle; `render_docx_bytes` and
`render_pdf_bytes` both render from that same list, so JSON, PDF, and
DOCX always agree on content. `app/api/routes/export.py` exposes this
as three GET endpoints, reading only from
`app/teaching_package/persistence.py` (a small additive
`load_teaching_bundle()` helper) — never re-invoking the AI pipeline.

## Engineering Decisions

**Why `BackgroundTasks` (and not, say, Celery/RQ):** the existing
pipeline is synchronous, in-process, single-worker code. `BackgroundTasks`
is the smallest change that lets `/api/v1/upload` return immediately
with a real `job_id` while a real job still runs and updates the same
`ProgressTracker` the rest of the code already uses — no new
infrastructure, no changed function signatures inside the pipeline
itself.

**Why polling (and not only SSE):** an SSE stream already existed
(`/api/v1/progress/{job_id}/stream`) but polling is simpler to reason
about from plain JavaScript, degrades gracefully on flaky connections,
and needs no reconnect logic. The SSE endpoint was left in place
unchanged for anyone who wants it.

**Why Jinja2 templates (and not React/Vue/Streamlit):** the assignment
explicitly asked for a simple, non-flashy interface using the existing
FastAPI app, and the project's own roadmap deliberately excludes
frontend frameworks for this kind of internal tool. Server-rendered
HTML plus a handful of small JS files is enough for six pages of mostly
static content plus one polling loop.

**Why no React:** matches the instruction to keep the implementation
simple and avoid unnecessary JavaScript frameworks; six mostly-static
pages don't need component state management.

**Why export from persisted JSON (and not re-running generation):** the
Teaching Package is already fully generated and saved to
`data/outputs/{document_id}.json` by `/upload`. Reading that file and
formatting it is instant and free; re-running generation to produce a
PDF/DOCX would duplicate AI calls for no benefit and risk producing a
document that disagrees with what's already on Results.

**Why a simple frontend:** the assignment scored engineering/UX
usability, not visual design; a plain, readable, accessible UI keeps
the diff small and every page easy to verify against the spec.

## Folder Additions

- `app/web/` — `__init__.py`, `routes.py` (page routes + 404 renderer)
- `app/api/routes/export.py` — JSON/PDF/DOCX download endpoints
- `app/utils/export_utils.py` — shared section-building + PDF/DOCX renderers
- `templates/` — `base.html`, `home.html`, `upload.html`, `progress.html`,
  `_progress_section.html`, `results.html`, `error.html`, `404.html`
- `static/css/style.css`
- `static/js/app.js`, `upload.js`, `progress.js`, `results.js`, `error.js`
- `tests/test_web_pages.py` — page-route tests
- `tests/test_export.py` — export-helper and export-endpoint tests

Modified (not new): `app/main.py` (static mount, web router, 404 handler),
`app/api/routes/upload.py` (background scheduling), `app/api/routes/progress.py`
(`result` field), `app/models/schemas.py` (`ProgressResponse.result`),
`app/core/constants.py` (`JobStage.GENERATING_PACKAGE`),
`app/progress/tracker.py` (stage-progress entry),
`app/teaching_package/persistence.py` (`load_teaching_bundle()` helper),
`tests/test_api.py` and `tests/test_teaching_package_api.py` (updated to poll
for the result now that `/upload` returns immediately).

## Testing

New automated coverage: `tests/test_web_pages.py` (all six pages return
200/404 as expected, static assets serve, Swagger loads) and
`tests/test_export.py` (section-building, DOCX/PDF byte-level output,
and the three export endpoints, including 404s for unknown documents).

Regression testing: `tests/test_api.py` and
`tests/test_teaching_package_api.py` were updated in place — not
rewritten — to match the new (intentionally asynchronous) `/upload`
contract; they still assert the same underlying facts (document id,
chunk count, classification, knowledge summary, teaching package
summary), just read via a progress poll instead of the old synchronous
response body. Every other existing test file (parsers, chunker,
classifier, knowledge extractor, teaching package generators/
orchestrator/persistence, validators, retriever, vectorstore, embeddings,
input router, prompt loader) is untouched, since none of them exercise
`/api/v1/upload`'s HTTP contract directly. Existing functionality — the
AI pipeline itself — was not modified, only when and how it's invoked
from the upload route.

## Known Limitations

- Single-user, local deployment target — no authentication, no user accounts
- No persistent database; the Teaching Package bundle is one JSON file per
  document under `data/outputs/`
- `ProgressTracker` is in-memory and single-process; progress state does not
  survive a restart and is not shared across multiple worker processes
- ChromaDB runs as local on-disk storage, not a managed/hosted instance
- No deployment/scaling setup included in this phase

## Future Scope

- Deploy the app (Render/similar) and record the live URL
- Replace the in-memory `ProgressTracker` with a durable store (Redis/SQL)
  if the app needs to run behind multiple workers
- Add authentication if the platform moves beyond single-user/local use
- Polish the PDF/DOCX export layout (branding, styling) beyond the current
  plain, readable format
