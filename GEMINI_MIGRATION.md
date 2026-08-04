# Gemini SDK Migration

## Summary

The Gemini integration was migrated off the deprecated `google-generativeai` SDK
onto Google's current officially-supported SDK, `google-genai`. This was a
compatibility fix only — no architecture, folder structure, or unrelated logic
was changed. The provider abstractions (`GeminiEmbeddingProvider`,
`GeminiTextGenerationProvider`) keep the exact same public interface, so
nothing outside `app/embeddings/` and `app/llm/` needed to change.

## Previous SDK

- Package: `google-generativeai==0.8.6` (pinned range `>=0.8.0,<0.9.0`)
- Import: `import google.generativeai as genai`
- Client pattern: module-level `genai.configure(api_key=...)`, then
  `genai.embed_content(...)` / `genai.GenerativeModel(name).generate_content(...)`
- Status: deprecated by Google; the SDK itself emits a deprecation warning
  pointing at `google-genai`. The embedding model this SDK was calling
  (`models/text-embedding-004` against the `v1beta` `embedContent` endpoint)
  is what was returning `404 ... is not found for API version v1beta`.

## New SDK

- Package: `google-genai` (pinned range `>=1.20.0,<2.0.0`)
- Import: `from google import genai`, `from google.genai import types`
- Client pattern: instantiated client object, `genai.Client(api_key=...)`,
  then `client.models.embed_content(...)` / `client.models.generate_content(...)`
- This is Google's current officially-supported Python SDK for the Gemini
  Developer API (the `PROJECT_ROADMAP.md` requirement of "Official Google
  Gemini SDK").

## Files Modified

| File | Change |
|---|---|
| `requirements.txt` | Replaced `google-generativeai>=0.8.0,<0.9.0` with `google-genai>=1.20.0,<2.0.0` |
| `app/embeddings/gemini_embeddings.py` | Re-implemented `_ensure_client` / `_embed_batch` against `google-genai`'s `Client().models.embed_content(...)` call shape. Same public interface (`EmbeddingProvider` protocol, `embed_documents`, `embed_query`, `dimensions`) preserved. |
| `app/llm/gemini_client.py` | Re-implemented `_ensure_client` / `generate_json` against `google-genai`'s `Client().models.generate_content(...)` call shape. Same public interface (`TextGenerationProvider` protocol, `generate_json`) preserved. |
| `app/config.py` | Updated default model names (see below). No new/removed settings fields. |
| `.env.example` | Updated `GEMINI_EMBEDDING_MODEL` and `GEMINI_GENERATION_MODEL` defaults to match. |
| `tests/test_embeddings.py` | Updated fakes to mimic `client.models.embed_content(model, contents, config)` returning an object with `.embeddings[i].values`, instead of the old module-level `genai.embed_content(model, content, task_type)` dict/object shape. Test coverage (batching, retries, empty input, missing key) is unchanged. |
| `tests/test_llm_client.py` | Updated fakes to mimic `client.models.generate_content(model, contents, config)`, instead of the old `genai.GenerativeModel(name).generate_content(prompt, generation_config=...)`. Test coverage (clean JSON, fenced JSON, retries, malformed JSON, non-object JSON, empty prompt, missing key) is unchanged. |

Nothing else (parsers, chunking, ChromaDB, retriever, routing, orchestration,
folder layout) was touched.

## Dependency Changes

```diff
- google-generativeai>=0.8.0,<0.9.0
+ google-genai>=1.20.0,<2.0.0
```

No other dependencies were added, removed, or re-pinned.

## Model Changes

| Setting | Old default | New default | Why |
|---|---|---|---|
| `gemini_embedding_model` / `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | `gemini-embedding-001` | `text-embedding-004` is the model the old SDK's `v1beta`/`embedContent` call was returning `404` for. `gemini-embedding-001` is the current Gemini embedding model, and `google-genai` does not require the `models/` prefix. |
| `gemini_generation_model` / `GEMINI_GENERATION_MODEL` | `models/gemini-2.5-flash` | `gemini-2.5-flash` | Same model family kept (per `PROJECT_ROADMAP.md`'s "Gemini 2.5 Flash" preference) — only the now-unnecessary `models/` prefix was dropped, since `google-genai` accepts bare model names. |

`gemini_embedding_dimensions` (default `768`) was left unchanged; it's now
passed through as `output_dimensionality` in `EmbedContentConfig`, which
`gemini-embedding-001` supports via Matryoshka truncation, so retrieval/
ChromaDB dimensionality is unaffected.

## API Changes

**Embeddings**

```diff
- genai.configure(api_key=...)
- genai.embed_content(model=..., content=batch, task_type=...)
+ client = genai.Client(api_key=...)
+ client.models.embed_content(
+     model=...,
+     contents=batch,
+     config=types.EmbedContentConfig(task_type=..., output_dimensionality=...),
+ )
```

Response shape changed from a dict/object with an `embedding` key to an
`EmbedContentResponse` with an `.embeddings` list, where each item exposes
`.values`. The provider normalizes this into the same `List[List[float]]`
return type callers already relied on.

**Text generation**

```diff
- genai.configure(api_key=...)
- model = genai.GenerativeModel(model_name)
- model.generate_content(prompt, generation_config={...})
+ client = genai.Client(api_key=...)
+ client.models.generate_content(
+     model=model_name,
+     contents=prompt,
+     config=types.GenerateContentConfig(
+         temperature=..., max_output_tokens=..., response_mime_type="application/json",
+     ),
+ )
```

`response.text` access, JSON parsing, and code-fence stripping are unchanged.

## Verification Steps

Outbound network access is not available in this execution environment, so a
live `pip install` / end-to-end run against the real Gemini API could not be
performed here. The following was done instead, and should be repeated by
whoever has network access before deploying:

1. **Static/syntax verification** — `python3 -m py_compile` on every changed
   file (`app/config.py`, `app/embeddings/gemini_embeddings.py`,
   `app/llm/gemini_client.py`, `tests/test_embeddings.py`,
   `tests/test_llm_client.py`). All compiled cleanly.
2. **Runtime logic verification** — built a minimal standalone harness with
   stub `google.genai` / `google.genai.types` modules that mirror the real
   SDK's public call shape (`Client(api_key=...)`,
   `client.models.embed_content(model, contents, config)` returning
   `.embeddings[i].values`, `client.models.generate_content(model, contents,
   config)` returning `.text`), and ran the two providers' actual code
   against it. Confirmed: batched embedding calls, query embedding, retry-
   then-succeed on a transient error, and missing-`GOOGLE_API_KEY` handling
   for the embedding provider; and clean-JSON parsing, fenced-JSON stripping,
   retry-then-succeed, and missing-`GOOGLE_API_KEY` handling for the
   generation provider.
3. **Unit test rewrite** — `tests/test_embeddings.py` and
   `tests/test_llm_client.py` were rewritten to mock the new
   `client.models.*` call shape (previously they mocked the old module-level
   `genai.embed_content` / `genai.GenerativeModel` shape). No other test file
   references the Gemini SDK, so no other tests needed changes.

### To finish verification with network access

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
# set a real GOOGLE_API_KEY in .env, then:
uvicorn app.main:app --reload
# upload a document via /api/v1/upload (Swagger UI) and confirm the
# pipeline reaches Embeddings -> ChromaDB -> Retriever -> Educational
# Classification -> Knowledge Extraction -> KnowledgeJSON -> Completed.
```

## Tests Executed

- `tests/test_embeddings.py` (rewritten, logic-verified via the standalone
  harness above — could not run under the real `pytest`/`chromadb`/`fastapi`
  stack without network access to install them).
- `tests/test_llm_client.py` (rewritten, logic-verified the same way).
- All other test files are untouched and were not affected by this
  migration (no other file imports the Gemini SDK).

## Bugs Fixed

- The root-cause bug: Gemini embedding calls were failing with
  `404 models/text-embedding-004 is not found for API version v1beta, or is
  not supported for embedContent`, because the deprecated
  `google-generativeai` SDK was calling a `v1beta` endpoint/model
  combination that Google no longer serves. Moving to `google-genai` with
  `gemini-embedding-001` resolves this.
- The `google-generativeai is deprecated. Please migrate to google-genai.`
  SDK warning is resolved, since the deprecated package is no longer a
  dependency.

## Final Result

The Gemini embedding and text-generation providers now call Google's current
officially-supported `google-genai` SDK, behind the same interfaces the rest
of the codebase already depended on. No architecture, routing, parsing,
chunking, ChromaDB, or retrieval code was touched. Full end-to-end
verification (`pip install` + `pytest` + a live upload through
Embeddings → ChromaDB → Retriever → Educational Classification → Knowledge
Extraction → KnowledgeJSON → Completed) should be re-run in an environment
with network access and a real `GOOGLE_API_KEY`, using the commands above.
