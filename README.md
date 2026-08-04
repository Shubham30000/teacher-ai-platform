# Teacher AI Platform

An AI-powered system that turns a raw educational document (a chapter, paper,
or set of notes) into a complete, classroom-ready **Teaching Package**:
lesson plan, teacher script, activities, assessment, and more — grounded in
the document you upload, with a browser interface to upload, watch progress,
and download the result.

## Project Overview

A teacher uploads a PDF/DOCX/PPTX/TXT document. The backend parses it,
classifies it (subject/grade/topic/chapter/difficulty), extracts structured
knowledge (objectives, concepts, definitions, formulae, examples,
misconceptions), and generates a nine-module Teaching Package from that
knowledge. The browser interface (Phase 2B) exposes this pipeline end to
end: upload, live progress, a results view with collapsible modules, and
JSON/PDF/DOCX downloads.

## Features

- Upload PDF, DOCX, PPTX, or TXT documents
- Automatic Educational Classification (subject, grade, topic, chapter, difficulty)
- Structured Knowledge Extraction, grounded in the source document
- Nine-module Teaching Package generation (lesson plan through teacher guidance)
- Real-time progress tracking (polling, backed by a real backend job)
- Browser UI: Home, Upload, Progress, Results, Error, and 404 pages
- Download the generated package as JSON, PDF, or DOCX
- Friendly, non-technical error handling (no stack traces surfaced to the user)

## System Architecture

```
Upload
  ↓
Input Router
  ↓
Parser (PDF/DOCX/PPTX/TXT)
  ↓
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
  ↓
Teaching Package Orchestrator
  ├─ Lesson Planner        ├─ Assessment
  ├─ Entry Ticket          ├─ Exit Ticket
  ├─ Teacher Script        ├─ Homework
  ├─ Blackboard Notes      └─ Teacher Guidance
  └─ Classroom Activity
  ↓
TeachingPackage → persisted as JSON in data/outputs/{document_id}.json
  ↓
Browser UI (Jinja2 + vanilla JS) → JSON / PDF / DOCX download
```

Ingestion and Teaching Package generation run in a FastAPI `BackgroundTask`
after `/api/v1/upload` returns, so the browser can poll
`/api/v1/progress/{job_id}` for real, live stage/percentage updates instead
of the request blocking until everything finishes.

## Folder Structure

```
app/
  main.py                 FastAPI app: routers, static mount, exception handlers
  config.py                Settings (env-driven)
  logging_config.py        Logging setup
  core/                     Exceptions, enums/constants (JobStage, etc.)
  web/                       Phase 2B: server-rendered page routes (Home/Upload/Progress/Results/Error)
  input_router/             Routes uploaded files to the correct parser
  parsers/                  PDF / DOCX / PPTX / TXT → StructuredDocument
  document_intelligence/    StructuredDocument, Section, Table, Image models
  chunking/                 Hierarchy-aware chunker
  embeddings/               Gemini embedding provider
  vectorstore/               ChromaDB wrapper
  retriever/                 Query API over the vector store
  llm/                        Gemini structured-JSON text-generation client
  prompt_engine/               Loads/renders prompts/*.md templates
  classification/               Educational Classification → DocumentMetadata
  knowledge_extraction/         Knowledge Extraction → KnowledgeJSON
  teaching_package/              9 generators + orchestrator + persistence
  progress/                  In-memory job progress tracker
  validation/                 Cross-cutting validation checks
  ingestion_service.py        Orchestrates router → chunk → embed → index → classify → extract
  api/routes/                 upload, progress, teaching_package, export, health
  models/schemas.py           API request/response models
  utils/                      File-handling helpers + export_utils.py (PDF/DOCX rendering)
templates/                  Phase 2B: Jinja2 page templates
static/css/, static/js/     Phase 2B: plain CSS + vanilla JS
prompts/                      Versioned prompt templates for classification, knowledge
                                extraction, and the 9 generators
tests/                        pytest suite (unit + integration)
data/uploads/, data/chroma_db/, data/outputs/   Runtime storage (gitignored)
```

## Installation

Requires **Python 3.10+**.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# edit .env and set GOOGLE_API_KEY (free key: https://aistudio.google.com/app/apikey)
```

## Environment Variables

See `.env.example` for the full, authoritative list of variables and their
defaults (API keys, model names, chunking parameters, upload limits, etc.).
Copy it to `.env` and fill in `GOOGLE_API_KEY` before running the app.

## Running Locally

```bash
uvicorn app.main:app --reload
```

- Browser UI: `http://127.0.0.1:8000/`
- Interactive API docs (Swagger): `http://127.0.0.1:8000/docs`

## Running Tests

```bash
./scripts/run_tests.sh
# or
pytest -v
```

Tests that need an unavailable dependency in your environment (`fitz`,
`fastapi`, `chromadb`) are automatically skipped via `pytest.importorskip`,
not silently faked.

## API Endpoints

| Method | Path                                       | Purpose                                              |
|--------|---------------------------------------------|-------------------------------------------------------|
| GET    | `/api/v1/health`                            | Health check                                          |
| POST   | `/api/v1/upload`                            | Upload a PDF/DOCX/PPTX/TXT file; runs the pipeline in the background and returns a `job_id` immediately |
| GET    | `/api/v1/progress/{job_id}`                 | Poll job progress (stage, percentage, and, once complete, the full result) |
| GET    | `/api/v1/progress/{job_id}/stream`          | Server-Sent-Events progress stream                     |
| POST   | `/api/v1/retrieve`                          | Query the vector store for relevant chunks             |
| GET    | `/api/v1/teaching-package/{document_id}`    | Fetch the persisted Teaching Package                    |
| GET    | `/api/v1/export/{document_id}/json`         | Download the full persisted bundle as JSON              |
| GET    | `/api/v1/export/{document_id}/pdf`          | Download the Teaching Package as a PDF                  |
| GET    | `/api/v1/export/{document_id}/docx`         | Download the Teaching Package as a DOCX                 |

## Browser Interface

Server-rendered with Jinja2 templates, plain CSS, and vanilla JavaScript
(no frontend framework):

- **Home** — project overview, supported formats, workflow diagram
- **Upload** — file picker with client-side validation (type, size, non-empty)
- **Progress** — polls `/api/v1/progress/{job_id}` and shows the real current
  stage and percentage; redirects to Results automatically on completion
- **Results** — document metadata, knowledge summary, and each generated
  module in a collapsible card, plus the three download buttons
- **Error** — friendly title/message/suggested action for any failure, with
  Retry and Back-to-Upload actions
- **404** — simple not-found page with a link back Home

## Teaching Package Modules

Nine modules are generated per document: **Lesson Plan**, **Entry Ticket**,
**Teacher Script**, **Blackboard Notes**, **Classroom Activity**,
**Assessment**, **Exit Ticket**, **Homework**, and **Teacher Guidance**. Each
module fails independently — one module failing does not block the rest of
the package.

## Export Features (JSON, PDF, DOCX)

The three download endpoints read the already-persisted, already-generated
bundle (`DocumentMetadata` + `KnowledgeJSON` + `TeachingPackage`) written by
`/upload` — they never call the AI pipeline again:

- **JSON** — the full raw bundle, as-persisted
- **DOCX** — built with `python-docx`
- **PDF** — built with PyMuPDF (`fitz`)

Both PDF and DOCX render from one shared set of formatted sections
(`app/utils/export_utils.py`), so the two formats stay consistent.

## Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| Backend Framework | FastAPI |
| Frontend | Jinja2 templates + vanilla JavaScript + plain CSS |
| LLM | Google Gemini (via `google-genai`) |
| Orchestration | LangChain |
| Vector Database | ChromaDB |
| Document Parsing | PyMuPDF, python-docx, python-pptx |
| Document Export | PyMuPDF (PDF), python-docx (DOCX) |
| Testing | pytest, httpx, Starlette TestClient |

## Current Limitations

- Single-process, in-memory job tracking — progress state is lost on restart and does not scale across multiple workers/processes
- No authentication or user accounts
- No persistent database — the Teaching Package bundle is stored as one JSON file per document under `data/outputs/`
- ChromaDB runs as local on-disk storage, not a managed/hosted instance
- Export PDFs/DOCX are simple, text-first layouts — not templated, branded documents
- If Teaching Package generation fails for a module, that module is simply omitted from the result (see `generation_errors` in the persisted bundle)

## Future Improvements

- Multi-agent orchestration with explicit role separation
- RAG citation/traceability surfaced directly in the Results page
- Curriculum alignment tagging (CBSE/ICSE/Common Core)
- Caching/batching of Gemini calls to reduce cost and latency
- A durable job store (Redis/SQL) in place of the in-memory tracker
- Authentication and per-user document history
- Richer, branded PDF/DOCX export templates

## License

No license file is included; this project is provided as-is for evaluation
purposes.
