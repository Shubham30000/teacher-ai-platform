# Phase 1A Verification Report

**Role:** Pre-release verification (Senior AI/SW Engineer, QA, DevOps, Code Review)
**Project:** Teacher AI Platform — Phase 1A (Document Ingestion & Retrieval Foundation)
**Verified against:** `PROJECT_ROADMAP.md`, IIT Mandi AI Engineer Assignment, IIT Mandi FAQ
**Scope of this pass:** verify, execute, debug, repair, document, stabilize — no new features, no
redesign of working modules.

---

## 1. Executive Summary

Phase 1A was **not** taken on faith. Every module was actually executed against real inputs
in a fresh environment — this is the first time the full `pytest` suite and a live FastAPI
server have been run for this codebase (the original `PHASE_1A_COMPLETION.md` explicitly
documents that its build environment had no network access and could not install `fastapi`,
`chromadb`, `pymupdf`, etc., so it relied on a duck-typed `pydantic` shim for logic-level
smoke tests instead).

Result: the implementation is fundamentally sound. Dependencies installed cleanly with no
resolver conflicts, the app boots, Swagger works, and **one genuine bug** was found and fixed
in the PDF parser's heading-detection heuristic (details in §7). After the fix, the full test
suite is green (64/64) and a live end-to-end run through a real server confirmed
parsing → structuring → chunking works correctly on a realistic NCERT-style document. A live
call to the real NCERT site confirmed the resolver's retry-then-degrade path behaves exactly
as designed. A handful of minor code-quality nits (unused imports, one dead test variable)
were also cleaned up.

**Verdict: ✅ READY FOR PHASE 1B** (see §16 for the reasoning and the two caveats attached to
that verdict).

---

## 2. Environment Used

- Fresh Linux container, no pre-installed Python packages for this project.
- Outbound network available to PyPI (`pypi.org`, `files.pythonhosted.org`) and to the general
  internet for HTTP(S) requests made by the app itself (e.g. `ncert.nic.in`), but **not** to
  `generativelanguage.googleapis.com` (Google's Gemini API) — that domain is not on this
  sandbox's egress allowlist. This matters for §5's embedding-stage result.

## 3. Python Version

Python 3.12.3 (`requirements.txt` requires ≥3.10 for `X | None` syntax — satisfied).

## 4. Dependency Installation Log

```
python3 -m venv .venv
pip install --upgrade pip
pip install -r requirements.txt
```

Installed cleanly, **zero version conflicts**, on the first attempt. All range-based
(not pinned) requirements resolved to mutually compatible versions, including chromadb's own
fastapi/starlette/pydantic constraints. Key resolved versions: `fastapi==0.119.1`,
`pydantic==2.13.4`, `chromadb==0.5.23`, `pymupdf==1.28.0`, `langchain==0.3.30`,
`google-generativeai==0.8.6`, `pytest==8.4.2`.

**No package version changes were necessary.** The requirements.txt's range-based pinning
strategy (explained in its own header comment) worked exactly as intended.

One dependency-level observation for the record, not a Phase 1A defect: `google-generativeai`
is now end-of-life upstream (a `FutureWarning` fires on import, pointing at the successor
`google-genai` package). Flagged in §9 and §15 — not changed here per the "do not redesign"
instruction, since the roadmap's tech stack section locks in the official Google SDK and
switching SDKs is a scope decision, not a bug fix.

## 5. Test Execution Summary

First run: **63 passed, 1 failed** (`tests/test_parsers_pdf.py::test_pdf_parser_extracts_headings_by_font_size`).
After the fix in §7: **64 passed, 0 failed**, in ~176s.

```
64 passed, 25 warnings in 176.29s
```

The 25 warnings are all either the `google-generativeai` deprecation notice (1 test) or a
`chromadb`-internal Pydantic-deprecation warning (24 tests, triggered inside chromadb's own
`types.py`, not this project's code) — informational, not failures.

**Live server run beyond pytest:** started the real `uvicorn` process and POSTed a real
synthetic NCERT-style `.docx` (headings, nested subsections, a table) to `/api/v1/upload`.
Server logs confirm real execution through routing → DOCX parsing → structuring → chunking
(3 chunks produced), at which point it correctly attempted a real call to Google's embedding
API and was blocked only by this sandbox's network allowlist (TLS handshake failures to
`generativelanguage.googleapis.com` — confirmed via server logs, not a guess). This is an
environment limitation, not an application defect; the embedding provider's logic itself
(batching, retry-with-backoff, missing-key handling) is separately covered by
`tests/test_embeddings.py` against a fake client and passes.

**Live NCERT resolver call:** also ran `NcertContentResolver.resolve()` directly against the
real `https://ncert.nic.in/textbook.php` (this domain **was** reachable from this sandbox).
It returned HTTP 403 on all 3 retry attempts, correctly fell back to the Playwright rendering
path, which failed because Chromium isn't installed in this sandbox
(`playwright install` was not run), and the resolver then correctly raised
`ContentResolutionError` with a clear message — exactly the graceful-degradation behavior the
roadmap requires (§9.1 of the completion doc flagged this as unverified; it is now
partially verified: the retry → fallback → graceful-failure *control flow* is confirmed live;
the actual DOM/selector parsing logic still hasn't been exercised against real NCERT HTML,
because the 403 prevented ever reaching a page body — see §9 Known Limitations, carried
forward).

## 6. Modules Verified

| Module | Verified how | Result |
|---|---|---|
| Repository structure | Compared against roadmap §7 folder layout | Matches |
| Configuration (`config.py`) | Real `pydantic-settings` load from `.env` | Works |
| Logging (`logging_config.py`) | Observed structured log output during live run | Works |
| FastAPI app / routing | Live server: `/health`, `/docs`, `/openapi.json` | 200 OK |
| Input Router | `pytest` + real DOCX upload through live server | Works |
| Topic Interpreter | Direct calls with 5 real phrasings incl. edge cases | Works (see §9) |
| Educational Content Resolver (NCERT) | Live call to real `ncert.nic.in` | Degrades correctly |
| PDF Parser | `pytest` (bug found + fixed) | Fixed, passes |
| DOCX Parser | `pytest` + live upload of real generated `.docx` | Works |
| PPTX Parser | `pytest` | Works |
| TXT Parser | `pytest` | Works |
| StructuredDocument | Exercised via all parser tests + live run | Works |
| Chunking | `pytest` + live run (3 chunks from real doc) | Works |
| Embeddings (Gemini) | `pytest` against fake client; live call blocked by sandbox network | Logic verified; live call environment-blocked |
| ChromaDB / vector store | `pytest` against real local ChromaDB | Works |
| Retriever | `pytest` | Works |
| Validators | `pytest` + direct call against a real parsed document | Works |
| API routes (`upload`, `topic`, `progress`, `retrieve`, `health`) | `pytest` + live server | Works |
| Progress tracking | Direct calls: create → update_stage → get_job, incl. not-found error | Works |
| Integration tests (`tests/`) | Full suite executed | 64/64 pass |

## 7. Bugs Found

**Bug 1 — PDF parser misclassifies headings on font-size ties (`app/parsers/pdf_parser.py`).**

`_estimate_body_font_size()` picked the document's "body text" font size using
`Counter.most_common(1)`. When multiple distinct font sizes each occur the same number of
times — which happens on any short or sparsely-sampled page, not just the test fixture —
`Counter` breaks the tie by first-insertion order. On a page where the title is rendered
before the body text, this silently selected the **title's** font size as "body text," which
made every line's size ratio ≤ 1.0, so nothing (not even the title) was classified as a
heading. This is a real correctness bug that would affect real short documents or the first
page of any document, not just synthetic test fixtures — the trigger condition (a tie in span
frequency) is common on pages with only a few lines of distinct-size text.

## 8. Bugs Fixed

**Fix for Bug 1:** among sizes tied for the highest frequency, the estimator now returns the
**smallest** one, on the reasoning that body text is virtually never the largest font on a
page — a safe, minimal tiebreak that doesn't change behavior on any page where a real mode
already exists (the vast majority of real multi-paragraph pages).

```python
# app/parsers/pdf_parser.py, _estimate_body_font_size
max_frequency = max(counts.values())
most_frequent_sizes = [size for size, freq in counts.items() if freq == max_frequency]
return min(most_frequent_sizes) if most_frequent_sizes else median(sizes)
```

Verified: `tests/test_parsers_pdf.py` now passes both tests; full suite re-run clean.

## 9. Files Modified

| File | Change | Reason |
|---|---|---|
| `app/parsers/pdf_parser.py` | Tie-break fix in `_estimate_body_font_size` | Bug 1 (§7) |
| `app/input_router/router.py` | Removed unused `Field`, `TopicExtractionError` imports | Dead code (`ruff` F401) |
| `tests/conftest.py` | Removed unused `Inches` import in the pptx fixture | Dead code (`ruff` F401) |
| `tests/test_parsers_txt.py` | `top_headings` was computed but never asserted on; added the missing assertion (that "Types of Force" is *not* a top-level heading) instead of deleting the line, since that was clearly the intended check | Dead code (`ruff` F841) — this was silently losing test coverage |
| `PHASE_1A_VERIFICATION_REPORT.md` | New file (this document) | Deliverable |

No other files were touched. No architecture, module boundaries, or working logic were
changed beyond the one real bug above.

## 10. Remaining Known Issues

Carried forward from `PHASE_1A_COMPLETION.md` §9 (still accurate) plus what this pass added:

1. **NCERT resolver DOM/selector logic still not live-verified end to end** — this pass
   confirmed the retry → Playwright-fallback → graceful-degradation *control flow* against the
   real site (it currently 403s all direct HTTP requests), but never reached a real page body,
   so the actual `<select>`/`<a>` scanning logic in `_find_book_link`/`_parse_chapter_links`
   remains verified only against hand-built fake HTML in `tests/test_content_resolver.py`.
   **Action before relying on Mode 2 in production:** run `playwright install chromium` and
   re-test against a real Class/Subject combination — the 403-then-Playwright-fallback path
   needs a working Chromium to actually succeed instead of degrading.
2. **Embedding/vector-store wiring to the real Gemini API is still not confirmed end-to-end**
   in *this* environment (blocked by network allowlist, not by the code) — the fix from this
   pass doesn't change that; it needs a real `GOOGLE_API_KEY` and outbound access to
   `generativelanguage.googleapis.com`.
3. **`google-generativeai` is deprecated upstream** (see §4). Not fixed here — flagged for a
   deliberate decision (stay pinned vs. migrate to `google-genai`) rather than an incidental
   change during a verification pass.
4. **`TopicInterpreter._extract_topic` produces an odd result on some conversational phrasing**
   — e.g. `"I want to teach something about history"` extracts the topic as
   `"I want to teach something about"` rather than `"history"` (which gets captured as the
   subject instead). This does **not** cause incorrect downstream behavior in Phase 1A: the
   result's `missing_fields` still correctly includes `grade`, so the system still asks the
   teacher for clarification rather than acting on the odd topic string. Cosmetic, low
   priority, safe to leave for Phase 1B if `_extract_topic`'s heuristics get revisited.
5. Token counting, in-memory single-process progress tracking, and the non-exhaustive subject
   alias list are unchanged from `PHASE_1A_COMPLETION.md` §9 items 3, 4, 6 — still accurate,
   not re-litigated here.

## 11. Architecture Compliance Review (vs. `PROJECT_ROADMAP.md`)

| Roadmap Phase 1 item | Status |
|---|---|
| Repository skeleton / config / `.env.example` | ✔ Complete |
| FastAPI app boots with health-check route | ✔ Complete |
| PDF/DOCX/PPT/TXT parsers individually working | ✔ Complete (PDF bug fixed this pass) |
| Document router selecting parser by classification | ✔ Complete |
| Educational Content Resolver (Mode 2, NCERT-first) incl. upload-fallback | ✔ Complete — control flow live-verified; selectors not live-verified (§10.1) |
| Chunking + embeddings + ChromaDB integration | ✔ Complete — chunking/vector-store live-verified; embeddings logic-verified only (§10.2) |
| Retrieval layer smoke-tested | ✔ Complete |
| **Educational classifier producing metadata** | ⚠ **Not implemented** — see discrepancy note below |
| **Knowledge extractor producing full Knowledge JSON** | ⚠ **Not implemented** — see discrepancy note below |

**Discrepancy worth recording, not fixed in this pass:** `PROJECT_ROADMAP.md`'s own Phase 1
scope (`## PHASE 1 — Foundation, Input Handling & Knowledge Ingestion`) explicitly lists
Educational Classification and Knowledge Extraction as Phase 1 modules and commit milestones
("Educational classifier producing metadata," "Knowledge extractor producing full Knowledge
JSON" both appear in the roadmap's own Definition of Done / commit milestones for Phase 1).
`PHASE_1A_COMPLETION.md` instead frames "Phase 1A" as a narrower ingestion-and-retrieval-only
slice and explicitly defers classification/extraction to "Phase 1B" — a scope split that
isn't recorded anywhere in the roadmap itself, which per the roadmap's own rules
(§0: "Do not add phases. Do not merge phases. Do not split phases.") should have been an
explicit, recorded amendment rather than an implicit one made only in the completion doc.
This verification pass did **not** implement classification/extraction to "fix" this, per the
explicit instruction to repair genuine implementation issues rather than add scope — but it
should be resolved deliberately (either amend the roadmap to reflect the narrower Phase 1A/1B
split, or treat classification+extraction as still-owed Phase 1 work) before Phase 1B
planning proceeds, so the two documents agree.

Everything else roadmap items 1–13 (per `PHASE_1A_COMPLETION.md` §3's own mapping) checks out
against the actual code, not just the completion doc's claims about the code.

## 12. IIT Mandi Assignment Compliance Review

| Assignment stage | Status per Phase 1A's declared scope | Independently confirmed |
|---|---|---|
| Stage 1: Document Intelligence (parsing, structure preservation) | Implemented | ✔ Yes — live parser runs, table/heading/hierarchy extraction confirmed |
| Stage 2: Educational Classification | Deferred to Phase 1B | — (see §11 discrepancy) |
| Stage 3: Knowledge Extraction | Deferred to Phase 1B | — (see §11 discrepancy) |
| Stages 4–8 (planning, generation, activities, assessment, gap analysis) | Out of scope (Phase 2 per roadmap) | Correctly absent |
| Stage 9: Validation | Partial — schema/structural validators exist; hallucination/grounding validation is a Phase 3 concern per roadmap | ✔ Implemented validators confirmed working |
| Stage 10: Publishing | Out of scope (Phase 3 per roadmap) | Correctly absent |
| Streaming Progress API | Implemented (`/progress/{job_id}`, `/progress/{job_id}/stream`) | ✔ Code-reviewed, matches assignment's example payload shape |
| Suggested architecture (API Gateway → Upload → Doc Intelligence → ... → Storage) | Followed for the ingestion slice | ✔ Matches |

No implementation goes beyond Phase 1A's declared scope (no lesson generation, no assessments,
no PDF outputs) — confirmed by reading `app/` end to end, not just the file listing.

## 13. Performance Observations

- Full `pytest` run: ~176s for 64 tests — dominated by a small number of retry/backoff tests
  in `test_embeddings.py` that intentionally sleep between simulated failures; no
  unexpectedly slow test found.
- Live ingestion of a multi-section DOCX with a table completed parsing → chunking in well
  under a second (per server timestamps in the log).
- `PdfParser._estimate_body_font_size` samples at most the first 15 pages, a reasonable bound
  already in place for large textbooks — not changed.
- No N+1-style or unbounded-loop patterns found in the modules reviewed.

## 14. Security Observations

- File uploads: `sanitize_filename` strips directory components (`Path(filename).name`) and
  restricts characters to a safe allowlist before ever touching the filesystem; extension is
  separately validated against a configured allowlist; size is capped; the saved path gets a
  random suffix to prevent overwrite collisions. No path-traversal issue found.
- No bare `except:` clauses anywhere in `app/`; every broad `except Exception` is explicitly
  annotated (`# noqa: BLE001`) as an intentional best-effort boundary (table/image extraction,
  SDK error normalization), not a swallowed-error anti-pattern.
- All custom exceptions funnel through one `TeacherPlatformError` hierarchy with a single
  FastAPI exception handler — consistent error shape, no risk of leaking stack traces to
  clients.
- `.env` / secrets: `GOOGLE_API_KEY` is read via `pydantic-settings` from environment/`.env`,
  never hardcoded; `.env` is gitignored.
- CORS is configured from `settings.cors_origins` rather than a hardcoded wildcard-with-credentials
  combination — reasonable for a project without auth per the roadmap's explicit exclusion of
  auth/login (§3).

No critical or high-severity issues found.

## 15. Recommendations

1. Resolve the roadmap-vs-completion-doc scope discrepancy in §11 explicitly before Phase 1B
   planning — pick one, record the decision.
2. Run `playwright install chromium` and do one live NCERT resolve against a real Class/Subject
   before depending on Mode 2 in a demo — see §10 item 1.
3. Confirm the embedding/vector pipeline against the real Gemini API with a real key and real
   network access (this sandbox couldn't) before considering ingestion "done" end-to-end.
4. Decide on a `google-generativeai` → `google-genai` migration path as a deliberate, tracked
   decision rather than letting the deprecation warning linger silently.
5. `TopicInterpreter._extract_topic`'s handling of conversational (non-roadmap-style) phrasing
   is a low-priority polish item, not a blocker — noted for whoever next touches that file.

## 16. Ready for Phase 1B?

## ✅ READY FOR PHASE 1B

**Reasoning:** Every module in Phase 1A's declared scope (per `PHASE_1A_COMPLETION.md`'s own
item list) exists, compiles, and — critically, unlike the previous pass — was actually
*executed*, not just read. The one real bug found (PDF heading misclassification on font-size
ties) is fixed and verified. The full test suite is green. A live server run confirmed the
core parsing → chunking pipeline works on a realistic document, and a live NCERT call
confirmed the resolver's failure-handling path behaves correctly under real-world conditions
(a 403 response) rather than only under mocked conditions.

**Two caveats attached to this verdict, not blocking it:**

- The roadmap/completion-doc scope discrepancy in §11 (classification + knowledge extraction)
  should be resolved as a recorded decision before Phase 1B work begins, so both documents
  agree on what Phase 1A did and did not include.
- The NCERT selector logic and the live Gemini embedding call remain unverified against the
  real external services in *any* environment so far (network-blocked here, no-network in the
  original build) — recommended as the first thing to confirm in an environment with full
  network access, per §15 items 2–3, before treating Mode 2 and the embedding pipeline as
  production-confirmed rather than logic-confirmed.

---

*This report reflects an actual execution pass — dependency install, full pytest run, live
server run with a real document upload, live calls to the real NCERT site, and direct
function-level smoke tests of the topic interpreter, progress tracker, and validators — not a
read-through of the code or of the previous completion report's claims.*
