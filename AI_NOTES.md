# AI_NOTES.md

## Purpose

This file is the handoff layer for future Codex sessions.

Read this file together with:

- `AGENTS.md`
- `README.md`
- `CURRENT_STATE.md`
- `CHANGELOG.md`, if present
- the design documents in `Design_documents/`

## Current Project State

The project has moved from pure design phase into the first implementation sprint.

Fresh-session baseline:

- `CURRENT_STATE.md` now contains the compact Session Handoff Baseline v1.
- A new session should read `AGENTS.md`, `README.md`, `AI_NOTES.md`, `CHANGELOG.md`, and `CURRENT_STATE.md`.
- Current verification baseline: `pytest: 186 passed`, `alembic: 0017_text_review_status (head)`.

Initial implementation exists:

- Python/FastAPI scaffold,
- `.venv`,
- `pyproject.toml`,
- `.env.example`,
- health endpoint,
- secure config loader,
- JSONL audit writer skeleton,
- secure storage path resolver,
- SQLAlchemy/psycopg DB layer,
- Alembic migration foundation,
- case create/list API,
- document/page/chunk persistence models and migration,
- immutable TXT import API,
- explicit imported-document processing validation run API,
- native-text PDF import foundation with configurable `docling_then_pypdf` parser profile,
- Docling optional dependency installed in `.venv` and explicit Docling PDF import smoke passed,
- explicit Tesseract OCR foundation for PDF documents with page/chunk versioning,
- backend-provided OCR recommendation metadata for PDF documents; the frontend shows OCR actions only when the backend marks OCR as recommended or optional, and optional OCR is labeled as an OCR check because it may duplicate/noise native text,
- document page/chunk detail endpoints list only current versions by default, keeping previous native/OCR versions auditably stored but out of the active working text view,
- native PDF import and OCR now stop at a `text_review_required` text layer with current pages but no current chunks; users explicitly create chunks after page review through the `chunk_document` workflow,
- image-only/scanned PDF imports without native text remain audit-tracked `review_required` documents for explicit OCR processing,
- average Tesseract confidence capture on a 0..1 scale and `low_ocr_confidence` quality warning,
- document page API returns OCR confidence as a numeric value and handles Decimal-backed DB values,
- generated local PDF samples and parser/OCR evaluation scripts,
- default upload limit raised to 50 MiB through `BOBERDETECTIVE_MAX_UPLOAD_BYTES`,
- deterministic TXT chunk creation during import,
- keyword search over document pages/chunks,
- source-reference persistence and quote validation,
- LLMProvider abstraction with LM Studio/OpenAI-compatible model-list smoke,
- analysis run provenance foundation,
- synthetic LLM model benchmark script,
- first generalized analysis module endpoint with `extract_claims` and `extract_events`,
- event persistence foundation,
- case review report API,
- JSON review report export foundation,
- HTML review report export foundation,
- export review workflow foundation,
- event review workflow foundation,
- shared review service helper,
- entity persistence foundation,
- `extract_entities` module foundation,
- entity review workflow foundation,
- review report filtering by object type, review status, and source validation status,
- review report export filters through `report_filters`,
- expanded review report source details with document metadata, offsets, chunk/page metadata, and bounded source excerpts,
- analysis module service split into common retrieval/JSON helpers and module-specific claim/event/entity/summary services,
- source-cited summary item persistence, source linkage, API, review workflow, and review report inclusion,
- `summarize_case` analysis module foundation with quote validation and summary item persistence,
- analysis module retrieval fallback for broader natural-language Hungarian prompts,
- local chunk indexing foundation through LM Studio/OpenAI-compatible embeddings and model-specific Qdrant collections, with `embed_chunks` analysis run provenance and chunk-level embedding metadata; model switches make chunks eligible for reindexing instead of incorrectly treating an old-model vector id as current,
- background chunk indexing through `POST /api/v1/cases/{case_id}/indexes/chunks/jobs`; the endpoint creates an `embed_chunks` analysis run and returns immediately, while FastAPI `BackgroundTasks` performs the LM Studio/Qdrant work,
- embedding index creation uses `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE` defaulting to `8`, so large documents are embedded and upserted in smaller LM Studio/Qdrant batches instead of one memory-heavy request,
- chunk index status is available through `GET /api/v1/cases/{case_id}/indexes/chunks/status`; the frontend uses it to show semantic index readiness, latest run progress, and block semantic/hybrid focused analysis until the active source scope is indexed with the configured embedding model,
- hybrid retrieval foundation through keyword, semantic, and hybrid strategies; batch-capable raw-chunk analysis modules can receive `retrieval_strategy`, and analysis run chunk inputs record `retrieval_match_type`,
- configured embedding model defaults to `text-embedding-qwen3-embedding-4b@q6_k`; embedding calls auto-ensure this model is loaded through LM Studio before `/v1/embeddings`; the previous 8B smoke loaded with `context_length=12288`, reindexed 49 Morgue PDF chunks into `boberdetective_chunks_text_embedding_qwen3_embedding_8b`, returned semantic hybrid-search hits, and a focused `extract_claims` smoke recorded `retrieval_strategy=hybrid` plus `retrieval_match_type=semantic` in analysis run provenance,
- live `summarize_case` smoke passed with the original broad query after retrieval fallback,
- contradiction candidate persistence, source linkage, API, review workflow, and review report inclusion,
- `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs,
- live `detect_contradiction_candidates` smoke passed on a two-claim time conflict sample,
- `detect_contradiction_candidates` now treats fewer than two source-valid claims as a clean `validation_status=warning` precondition result, records claim-selection metadata as analysis run input, and avoids an unnecessary LLM call,
- `detect_contradiction_candidates` now builds deterministic backend-selected claim pairs, applies safe fetch/pair limits, supports meaningful focus filtering over claim/source text, records selected pair mappings in analysis run metadata, and rejects model output that references unselected pairs,
- `detect_contradiction_candidates` requires focus text. It uses `contradiction_candidate_limit` for its candidate cap, while raw-chunk modules use `max_chunks`. Its focus filter works on already extracted claim text/source quotes, keeps Hungarian accents, accepts non-stopword terms from two characters, and does not use the chunk semantic/hybrid retrieval selector,
- contradiction candidate validation now deduplicates same claim-pair/type candidates, caps most model-proposed `high` severities to `medium`, and replaces model-written titles/descriptions with conservative pair-bound text generated from the two selected source-cited claims,
- `detect_contradiction_candidates` supports `claim_review_scope`; default `reviewable` uses source-valid claims with review status `new`, `needs_review`, `verified`, or `corrected`, excluding `rejected`,
- `detect_contradiction_candidates` now requires explicit contradiction qualification: persisted candidates need `is_contradiction_candidate=true` and a concrete `conflict_basis`; contextual/non-conflicting pairs are rejected or carried as unsupported items,
- manual contradiction candidate creation now exists as a separate claim-pair workflow: the frontend exposes `Kezi ellentmondasjelolt`, only source-valid/non-rejected claims are selectable, selected claim text and sources are readonly-previewed, and the backend persists the candidate through a `manual_entry` analysis run,
- historical deduplication now skips already persisted, content-matched review outputs across repeated analysis runs for claims, events, summary items, missing item candidates, and contradiction candidates,
- entity extraction automatically merges only exact/normalized repeated entities into the existing entity review object and links additional occurrences as mentions/sources,
- ambiguous entity identity decisions should be handled through the explicit entity merge workflow, not by automatic alias guessing,
- frontend entity merge is available both from report item cards and the object detail panel; merge target selection uses the full case entity list, not only currently filtered report items,
- event merge follows the same human-reviewed pattern: `event_merged` audit event, source links moved to the target event, source event marked `corrected`, and frontend merge controls use the full case event list,
- missing item candidate merge follows the same human-reviewed pattern: `missing_item_candidate_merged` audit event, source links moved to the target candidate, source candidate marked `corrected`, and frontend merge controls use the full case missing item candidate list,
- entity, event, and missing item candidate source links can be detached manually through audit-tracked `detach_source` review actions; frontend source details show `Levalasztas` only when a concrete source-link id is available,
- detached source links are parked in `detached_source_items` with the source reference plus object/source snapshots, and the frontend shows them under `Levalasztott forrasok`,
- detached sources can be reattached from the parked-source panel or marked irrelevant; source details can also directly move a source to another same-type target object without a manual detach/reattach round,
- users can select readonly text from document chunks and create source-bound manual claim/entity/event/missing item candidate objects through `manual_entry` provenance runs,
- detached source items can also create new source-bound manual claim/entity/event/missing item candidate objects and then store the created object as their handled target,
- missing item candidate persistence, source linkage, API, review workflow, and review report inclusion,
- `detect_missing_items` analysis module foundation over source-cited chunk quotes,
- live `detect_missing_items` smoke passed on a referenced attachment/photo documentation sample,
- missing item candidate JSON/HTML export smoke coverage,
- analysis retrieval fallback improvement for short/inflected Hungarian query terms,
- minimal React/Vite frontend workbench scaffold,
- frontend review actions for review report items,
- frontend source detail and review history display for report items,
- frontend long-running operation feedback with elapsed time and last action summary,
- frontend document list and analysis run history views,
- frontend document page/chunk and analysis run input/output drill-down with human-readable selected-source and output summaries,
- frontend TXT/PDF import selection and OCR action for review-required/no-page PDF documents,
- frontend source scope controls for batch-capable `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, and `detect_missing_items`,
- frontend contradiction-candidate UI now reflects the claim-pair workflow: the analysis panel requires focus and exposes claim review scope plus contradiction candidate cap for contradiction detection, claim-selection metrics and selected pairs are rendered in analysis run details, analysis summaries show claim-pair based execution, and review report items include a conservative review note,
- frontend analysis focus text starts empty for every module; module-specific examples are placeholders only and are not sent as query text unless the user types actual text,
- frontend review filter controls and object detail panel,
- frontend export history and review report filter controls,
- pytest smoke tests.

Completed design documents:

- `Design_documents/00_project_context_for_codex.md`
- `Design_documents/01_concept_and_mvp_requirements.md`
- `Design_documents/02_technical_architecture_v1.md`
- `Design_documents/03_database_schema_v1.md` with v1.1 pre-implementation refinements folded in
- `Design_documents/03a_database_schema_pre_implementation_review.md`
- `Design_documents/04_runtime_and_deployment_v1.md`
- `Design_documents/05_api_design_v1.md`
- `Design_documents/06_document_processing_pipeline_v1.md`
- `Design_documents/07_prompt_and_json_schema_collection_v1.md`
- `Design_documents/08_mvp_backlog_and_implementation_sequence.md`
- `Design_documents/09_environment_verification_and_security_baseline.md`
- `Design_documents/10_analysis_batch_processing_plan.md`

## Project Summary

The project is a fully local, auditable investigative document intelligence system.

It is meant to process case-related documents and create structured, source-cited, human-reviewable outputs:

- document inventory,
- entities and mentions,
- event timeline,
- claims,
- contradiction candidates,
- missing item candidates,
- source-cited summaries,
- exports.

The system must not make autonomous legal or investigative decisions.

## Core Constraints

The most important design constraints:

- local-first / offline-capable,
- no cloud dependency,
- sensitive-data-safe,
- original documents immutable,
- page-level text stored,
- chunks stored and searchable,
- every AI-generated object source-cited,
- every AI-generated object traceable to an analysis run,
- human review required for meaningful use,
- exports must be auditable,
- legal RAG is later, not MVP-1.

Mandatory rule:

```text
No source -> no claim.
```

## Runtime Direction

The current runtime direction is:

```text
Windows 11 host:
  - VS Code / Codex / browser
  - LM Studio native runtime

WSL2 Ubuntu:
  - application runtime
  - backend
  - workers
  - PostgreSQL
  - Qdrant
  - document processing
  - OCR / NLP
  - audit logs
  - exports
```

LM Studio is now the default development LLM provider.

The backend must use an `LLMProvider` abstraction so LM Studio can later be replaced by:

- Ollama,
- llama.cpp / llama-server,
- another local runtime.

## Database Schema Review Notes

The database schema v1 is already drafted, and the main schema document has been updated with the review's most important pre-implementation refinements.

The incorporated refinements are:

1. Add page/chunk versioning:
   `version_no`, `is_current`, `superseded_by_id`.
2. Make `summary_items` an MVP table, not just optional.
3. Add `summary_item_sources`.
4. Add `source_validation_status` to AI-output tables.
5. Keep `source_references` as a central table.
6. Keep `analysis_runs` as the central provenance table.
7. Use `text + CHECK` instead of PostgreSQL ENUM in early migrations.
8. Do not implement trigger-based audit in the first MVP.
9. Use explicit application-level audit service plus append-only JSONL.

## WSL Migration Context

The user has created or prepared a dedicated WSL2 Ubuntu environment.

The intended WSL-side project location is:

```text
~/projects/Codex_BoberDetective
```

The intended data location is:

```text
~/boberdetective-data
```

The user may manually copy this repository into the WSL path and then open it with:

```bash
cd ~/projects/Codex_BoberDetective
code .
```

Future sessions should assume the project may now be opened from WSL rather than the original Windows path.

Previously unverified items now checked:

- WSL can reach the Windows-hosted LM Studio API at `http://127.0.0.1:1234/v1`.
- Whether LM Studio embedding support is sufficient, or a separate embedding provider is needed.
- Whether the selected local model is good enough for Hungarian claim/event/contradiction extraction.
- User-side semantic/hybrid retrieval smoke after switching to `text-embedding-qwen3-embedding-4b@q6_k` found no obvious quality regression so far; observed limitations align with planned ranking and source-mode hardening rather than a clear model failure.
- Document/case source modes now use retrieval-aware source selection from explicit focus text. Empty focus is rejected for raw-chunk modules so large cases are not processed blindly; document-mode retrieval is constrained to the selected document.
- Raw-chunk source-selection query variants keep Hungarian accents and accept non-stopword terms from two characters; the original focus text remains the first retrieval query.
- Raw-chunk analysis source selection supports `page_start` / `page_end` filters only inside selected-document source scope. Page filtering uses overlap logic and is wired through keyword, semantic, and hybrid retrieval; it is not a separate source mode.
- Whole-case raw-chunk analysis has no page-range fields or backend page-range requirement. Selected-document analysis defaults to document page bounds in the frontend; if API callers omit page fields for document scope, the backend uses the full document and rejects only out-of-document ranges.
- User-side retrieval/analysis smoke after selected-document page-range filtering produced especially precise results, making this workflow the current preferred path for large documents when the user knows the approximate page interval.

## Suggested Next Steps

Likely next steps, in order:

1. Read the handoff docs and design documents.
2. Decide and implement document parking/deletion/archive behavior for accidentally imported, badly processed, or intentionally excluded documents.
3. Add frontend source-selection visibility for analysis runs: document, chunk index, match type, score, and selected-source preview.
4. Consider durable job supervision if indexing grows beyond FastAPI background tasks.

Strategic rationale:

- The frontend is currently usable enough for the MVP workflow and now has Hungarian visible labels.
- The document ingestion foundation now handles native PDF parsing, explicit OCR, review-required states, confidence metadata, and medium scanned PDF uploads well enough to move forward.
- The raw-chunk analysis modules are now batch-capable and live-smoke passed on document/case source modes.
- Contradiction detection is downstream of source-cited claims, so it should remain claim-pair based and preserve `no source -> no claim` through claim/source-reference provenance.

Environment verification notes:

- WSL Ubuntu 24.04 is ready.
- Python 3.12, Git, Node/npm, curl, Make, Docker CLI, Docker Compose, PostgreSQL CLI, Tesseract, and ShellCheck are available.
- Git repository is initialized on branch `main` and tracks `origin/main`.
- Docker daemon access works for `bober`.
- PostgreSQL and Qdrant are running through Docker Compose.
- PostgreSQL is reachable at `127.0.0.1:5432`.
- Qdrant is reachable at `127.0.0.1:6333`.
- Tesseract has `hun` language data installed.
- LM Studio is reachable from WSL at `http://127.0.0.1:1234/v1`.

Implementation status:

- `.venv` exists and project dependencies are installed.
- `pyproject.toml` and `.env.example` exist.
- Initial FastAPI scaffold exists under `app/`.
- Health endpoint works.
- SQLAlchemy/psycopg DB layer exists.
- Alembic migrations through `0017_text_review_status` are applied.
- `users`, `cases`, `case_users`, `audit_events`, `documents`, `document_pages`, `document_chunks`, `source_references`, `analysis_runs`, `analysis_run_inputs`, `analysis_run_outputs`, `claims`, `claim_sources`, `entities`, `entity_mentions`, `human_reviews`, `events`, `event_sources`, `exports`, `export_items`, `summary_items`, `summary_item_sources`, `contradiction_candidates`, `contradiction_candidate_sources`, `missing_item_candidates`, and `missing_item_candidate_sources` tables exist.
- Case create/list API works.
- Case creation writes DB audit event and JSONL audit event.
- Document/page/chunk persistence foundation exists.
- Immutable TXT import works through `POST /api/v1/cases/{case_id}/documents`.
- Native-text PDF import works through `POST /api/v1/cases/{case_id}/documents` using `BOBERDETECTIVE_PDF_PARSER`; the default `docling_then_pypdf` profile prefers Docling when installed and falls back to local `pypdf`.
- Explicit `BOBERDETECTIVE_PDF_PARSER=docling` import smoke passed with parser `docling` and `parse_document` validation `passed`.
- PDF parser hardening now covers multi-page native PDFs, corrupt PDFs, partially empty PDFs, and image-only PDFs; partially empty native-text PDFs and no-native-text PDFs become `review_required` with analysis run validation `warning`.
- The Docling adapter uses native-text mode with OCR/table/remote services disabled, but the first run downloaded local model artifacts; offline deployments should pre-cache these dependencies/artifacts.
- Explicit document processing validation works through `POST /api/v1/cases/{case_id}/documents/{document_id}/process`.
- Explicit PDF OCR works through `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr` with `ocr_document` analysis run provenance.
- OCR test coverage includes a generated scanned-style/image-only PDF fixture: native parsing reports no source text, then Tesseract extracts OCR text from the rendered page.
- OCR API smoke passed: document `processed`, run `ocr_document`, validation `passed`, and current page text source `ocr`.
- Synthetic PDF samples exist under `samples/pdf/`: native-text, good scanned, weak scanned, and mixed empty-page PDFs.
- `scripts/evaluate_pdf_samples.py` reports native parse outcome, OCR text length, confidence, and quality issues; current weak scanned sample triggers `low_ocr_confidence`.
- Frontend now exposes backend OCR recommendations and a separate `Szovegreszek letrehozasa` action for `text_review_required` documents; after OCR it refreshes document status/pages, and after chunk creation it refreshes chunks and analysis run history.
- `Design_documents/10_analysis_batch_processing_plan.md` defines the analysis architecture step; the first backend slice now supports source selection modes, chunk batching, and batch-capable `extract_claims`.
- Latest live batch analysis smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, returned `validation_status=passed`.
  - `case` source mode selected 6 chunks across the smoke case, ran 3 batches with `batch_size=2`, returned `validation_status=passed`.
  - Analysis run inputs include `batch_index`, `batch_count`, `chunk_labels`, `source_label`, and `retrieval_score`.
- Latest live batch `extract_events` smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, returned `validation_status=passed`.
  - `case` source mode selected 4 chunks, ran 2 batches with `batch_size=2`, returned `validation_status=passed`.
- Semantic `extract_events` has an effective batch-size cap of 2 chunks to avoid local LM Studio chat timeouts on larger semantic result sets. Live regression: query `gyilkossággal esettel kapcsolatos események`, `max_chunks=10`, `retrieval_strategy=semantic`, requested `batch_size=5`; the run completed in about 262s, selected 10 chunks, returned source-cited events, and finished `validation_status=warning` due to unsupported notes rather than timeout.
- Latest live batch `extract_entities` smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, returned `validation_status=passed`.
  - `case` source mode selected 4 chunks, ran 2 batches with `batch_size=2`, returned `validation_status=passed`.
  - Case-mode audit check showed 4 chunk inputs, batch indexes `[1, 1, 2, 2]`, and 30 output records.
- Latest live batch `summarize_case` smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, returned `validation_status=passed`.
  - `case` source mode selected 4 chunks, ran 2 batches with `batch_size=2`, returned `validation_status=passed`.
  - Summary prompt is stricter than extraction prompts: batch output is capped at 3 summary items and body/title must stay directly supported by `quote_text`.
- Latest live batch `detect_missing_items` smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, returned `validation_status=passed`.
  - `case` source mode selected 4 chunks, ran 2 batches with `batch_size=2`, returned `validation_status=passed`.
  - Case-mode audit check showed 4 chunk inputs, batch indexes `[1, 1, 2, 2]`, and 20 output records.
- Focused `extract_events` regression checked with query `narrátor Dupin`: the original failure came from invalid LLM JSON caused by an unescaped double quote inside `quote_text`; the event prompt now asks for shorter exact excerpts, valid JSON escaping, allowed enum values, and avoiding double-quote-containing excerpts when possible. Retest returned `HTTP 200` and `validation_status=passed`.
- Frontend now exposes source scope controls for batch-capable `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, and `detect_missing_items`: selected document, whole case, selected-document page range, required focus text, `Szovegresz plafon` defaulting to 20 and capped at 30, and batch size. `detect_contradiction_candidates` keeps its claim-pair workflow with required focus.
- Frontend analysis run details render selected chunk inputs as Hungarian source summaries with document/page/chunk, retrieval match type/score, batch position, and preview text. Output rows also show short object summaries. `input_kind=claim_selection` payloads remain rendered as Hungarian claim-selection summaries with selected pair rows; claim inputs show which selected pairs include the claim.
- Frontend analysis panel marks contradiction focus as required, shows a claim-pair module note, and exposes `Allitaskor` (`reviewable`, `verified`, `needs_review`, `all_source_valid`) plus `Ellentmondasjelolt plafon` for `detect_contradiction_candidates`; analysis summaries show `claim-par alapu` instead of implying raw chunk selection.
- Frontend focus placeholders are informational only; raw-chunk module runs are disabled until the user types focus text, and the backend enforces the same rule.
- Frontend contradiction report items and detail view show a conservative note that the object is an ellenorizendo jelolt, not a proven contradiction.
- TXT import stores the original bytes under UUID-based immutable storage paths.
- TXT import creates the first `document_pages` record.
- TXT import still creates deterministic page-local `document_chunks` directly. Native PDF import and OCR create current pages first, then explicit chunk creation produces page-local `document_chunks` with `char_window_v2`; chunking stays within a single processed page for source-location fidelity, prefers paragraph breaks, then sentence-end breaks, then line breaks/spaces before a hard character limit.
- Document chunks are available through `GET /api/v1/cases/{case_id}/documents/{document_id}/chunks`.
- TXT import writes DB + JSONL audit with chunk count metadata.
- Keyword search works through `POST /api/v1/cases/{case_id}/search/keyword`.
- Keyword search uses PostgreSQL full-text search over current pages/chunks with parameterized SQLAlchemy queries.
- Keyword search returns source object identifiers, document metadata, page ranges, scores, and plain-text quotes.
- Source references work through `POST /api/v1/cases/{case_id}/source-references`.
- Source reference validation works through `POST /api/v1/cases/{case_id}/source-references/validate`.
- Source reference creation validates page/chunk ownership and quote presence/span before persistence.
- Source reference creation writes DB + JSONL audit.
- LLMProvider abstraction exists in `app/services/llm.py`.
- LM Studio smoke works through `GET /api/v1/system/llm/smoke`.
- Current LM Studio smoke result: reachable at `http://127.0.0.1:1234/v1`; configured chat and embedding models are available.
- Analysis run list/detail API works through `GET /api/v1/cases/{case_id}/analysis-runs`.
- Analysis run lifecycle helpers write started/succeeded/failed/cancelled audit events.
- Analysis run inputs and outputs can explicitly record the source objects used and produced by a run.
- Synthetic LLM benchmark exists at `scripts/run_llm_benchmark.py`.
- Benchmark result from 2026-05-11 with OpenAI-compatible `/v1/chat/completions`: `meta-llama-3.1-8b-instruct` reached `10/12` on the tuned source-faithfulness smoke; `qwen/qwen3.5-9b` produced empty final `content` because reasoning output consumed the response path.
- Benchmark result from 2026-05-12 with LM Studio native `/api/v1/chat` and `reasoning: "off"` for Qwen: final run gave `qwen/qwen3.5-9b` `12/12` in 18.3s and `meta-llama-3.1-8b-instruct` `10/12` in 6.2s.
- Current interpretation: Qwen is the better first quality candidate when called through LM Studio native API with reasoning disabled; Llama remains the faster fallback/control model.
- LM Studio native API notes captured in `Design_documents/04_runtime_and_deployment_v1.md`: use `max_output_tokens`, not `maxTokens`; prefer `store: false`; prefer `system_prompt`; send `reasoning: "off"` only for reasoning-capable models such as Qwen.
- Backend now supports explicit LM Studio native chat-model loading through `POST /api/v1/system/llm/load-chat-model`.
- LM Studio native chat calls now auto-ensure the configured chat model is loaded before sending `/api/v1/chat`; loaded instance ids are reused when present, and the configured load profile is applied only when no matching instance is loaded.
- Current preferred chat-model LM Studio load profile is configured as `context_length=12288`, `eval_batch_size=6144`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`.
- Embedding model load uses `context_length=12288`; LM Studio currently rejects `eval_batch_size`, `flash_attention`, and `offload_kv_cache_to_gpu` for embedding models, so those are intentionally not sent for embedding load.
- Latest empty-state model-load smoke accepted the reduced profile: `text-embedding-qwen3-embedding-4b` loaded in 3.461s and `qwen/qwen3.5-9b` loaded in 16.942s with `eval_batch_size=6144`.
- Live model-load smoke accepted the profile and returned `qwen/qwen3.5-9b:2`, `status=loaded`, `load_time_seconds=10.784`, with echoed `parallel=4`.
- Future native provider refinement: switch benchmark/runtime payload from locally tested `input.type="text"` to documented `input.type="message"` if local testing confirms compatibility.
- First source-cited analysis smoke works through `POST /api/v1/cases/{case_id}/analysis/source-cited-smoke`.
- The smoke endpoint retrieves a chunk by keyword search, records query/chunk as analysis run inputs, calls Qwen through LM Studio native API with reasoning disabled, validates quote text against the chunk, creates a source reference, persists a claim, records outputs, and finishes the run with validation status.
- Claims work through `GET /api/v1/cases/{case_id}/claims` and `GET /api/v1/cases/{case_id}/claims/{claim_id}`.
- Claim creation requires a same-case analysis run and source reference in service logic.
- Live smoke result: `analysis 200`, `validation_status=passed`, claim persisted with one source, `source_validation_status=source_valid`.
- Claim review works through `POST /api/v1/cases/{case_id}/claims/{claim_id}/reviews`.
- Supported claim review actions now: `verify`, `reject`, `mark_needs_review`, `comment`.
- Claim review writes append-only `human_reviews` records and `claim_review_recorded` audit events.
- Live review smoke result: claim moved to `verified`, review history count 1.
- Generalized analysis module execution now exists through `POST /api/v1/cases/{case_id}/analysis/modules/{module_key}`.
- Currently supported module keys: `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, `detect_missing_items`, `detect_contradiction_candidates`.
- Analysis module implementation is split across `app/services/analysis_module_common.py`, `analysis_module_claims.py`, `analysis_module_events.py`, `analysis_module_entities.py`, `analysis_module_summaries.py`, `analysis_module_missing_items.py`, and `analysis_module_contradictions.py`; `analysis_modules.py` remains the thin public facade for API and compatibility imports.
- The `extract_claims` module performs keyword chunk retrieval, records query/chunk inputs, calls LM Studio native with the `extract_claims_v1` prompt, validates each returned quote against the labeled source chunk, creates source references, persists claims, records outputs, and finishes the analysis run.
- The `extract_events` module performs keyword chunk retrieval, records query/chunk inputs, calls LM Studio native with the `extract_events_v1` prompt, validates each returned quote against the labeled source chunk, creates source references, persists events/event_sources, records outputs, and finishes the analysis run.
- The `extract_entities` module performs keyword chunk retrieval, records query/chunk inputs, calls LM Studio native with the `extract_entities_v1` prompt, validates each returned mention quote against the labeled source chunk, creates source references, persists entities/entity_mentions, records outputs, and finishes the analysis run.
- The `summarize_case` module performs keyword chunk retrieval, records query/chunk inputs, calls LM Studio native with the `summarize_case_v1` prompt, validates each returned quote against the labeled source chunk, creates source references, persists summary_items/summary_item_sources, records outputs, and finishes the analysis run.
- The `detect_contradiction_candidates` module takes existing source-cited claims, builds deterministic selected claim pairs, records claim-selection/pair metadata and selected claims as analysis inputs, calls LM Studio native with the `detect_contradiction_candidates_v1` prompt only when at least one selected pair exists, validates returned claim labels against the selected pair set, persists contradiction_candidates/contradiction_candidate_sources, records outputs, and finishes the analysis run.
- Empty/precondition smoke result: on a case with 0 source-valid claims, `detect_contradiction_candidates` returned `HTTP 200`, `validation_status=warning`, 0 candidates, an unsupported item explaining that at least two source-valid claims are required, and an analysis run `filter` input with `input_kind=claim_selection`.
- Claim-rich pair-selection smoke result: on case `a9ccf14e-093d-40db-970e-856e19df826f`, focused query `Kovacs Anna Nagy Peter telefonhivas` selected 8 fetched claims, 6 focus-matched claims, 8 backend-selected pairs, returned `HTTP 200`, `validation_status=passed`, and 2 `time_conflict` candidates.
- Latest contradiction quality smoke on the same case returned conservative deterministic titles, pair-bound descriptions from the two selected claim texts, and `severity_hint=medium` for time conflicts.
- Latest contradiction qualification smoke returned `HTTP 200`; the model marked some selected pairs as unsupported because they were related but not conflicting, while time-conflict-like pairs were still persisted as conservative `medium` candidates.
- Live `detect_contradiction_candidates` smoke result: imported a TXT sample with two different phone call times, `extract_claims` produced 2 source-cited claims, contradiction detection returned `analysis 200`, `validation_status=passed`, 1 `time_conflict` candidate with 2 source references.
- Review report smoke for `object_type=contradiction_candidate` returned the candidate with expanded source details.
- Analysis module retrieval now tries the original query, a normalized significant-term query, and individual normalized terms. This keeps the public search API strict while making analysis modules less brittle for natural Hungarian prompts.
- Live `summarize_case` smoke result: the original broad/accented query now returned `analysis 200`, `validation_status=passed`, 3 persisted summary items, all `needs_review` and `source_valid`.
- Review report smoke for `object_type=summary_item` returned 3 source-cited summary items with expanded source details.
- Unsupported module keys are rejected before execution.
- Event list/detail works through `GET /api/v1/cases/{case_id}/events` and `GET /api/v1/cases/{case_id}/events/{event_id}`.
- Event review works through `POST /api/v1/cases/{case_id}/events/{event_id}/reviews`.
- Supported event review actions: `verify`, `reject`, `mark_needs_review`, `comment`.
- Event review updates `events.review_status`, writes append-only `human_reviews` records, and writes `event_review_recorded` audit events.
- Live event review smoke result: `review 200`, event moved to `verified`, review history count 1.
- Entity list/detail works through `GET /api/v1/cases/{case_id}/entities` and `GET /api/v1/cases/{case_id}/entities/{entity_id}`.
- Live `extract_entities` module smoke result: `analysis 200`, `validation_status=passed`, 2 persisted person entities with mentions and source references.
- Entity review works through `POST /api/v1/cases/{case_id}/entities/{entity_id}/reviews`.
- Supported entity review actions: `verify`, `reject`, `mark_needs_review`, `comment`.
- Entity review updates `entities.review_status`, writes append-only `human_reviews` records, and writes `entity_review_recorded` audit events.
- Live entity review smoke result: `review 200`, entity moved to `verified`, review history count 1.
- Shared review helper exists in `app/services/reviews.py`.
- Claim, entity, event, and export review workflows now use the shared helper for status mapping, review history listing, append-only review record creation, and audit writing.
- Summary item list/create/detail/review API exists through `/api/v1/cases/{case_id}/summary-items`.
- Summary item creation requires same-case `analysis_run_id` and `source_reference_id`; no source-free summary item creation path exists.
- Summary item reviews use append-only `human_reviews` with `object_type=summary_item`.
- Summary items are included in the case review report and can be selected through `object_type=summary_item`.
- Contradiction candidate list/create/detail/review API exists through `/api/v1/cases/{case_id}/contradiction-candidates`.
- Contradiction candidate creation requires a same-case analysis run, at least two same-case source references, and either a same-case claim pair or event pair.
- Contradiction candidate reviews use append-only `human_reviews` with `object_type=contradiction_candidate`.
- Contradiction candidates are included in the case review report and can be selected through `object_type=contradiction_candidate`.
- Missing item candidate list/create/detail/review API exists through `/api/v1/cases/{case_id}/missing-item-candidates`.
- Missing item candidate creation requires a same-case analysis run and at least one same-case source reference.
- Missing item candidate reviews use append-only `human_reviews` with `object_type=missing_item_candidate`.
- Missing item candidates are included in the case review report and can be selected through `object_type=missing_item_candidate`.
- `detect_missing_items` works through `POST /api/v1/cases/{case_id}/analysis/modules/detect_missing_items`.
- `detect_missing_items` uses keyword chunk retrieval, LM Studio native execution, quote validation, source-reference creation, missing-item candidate persistence, and analysis run provenance.
- Live `detect_missing_items` smoke result: `analysis 200`, `validation_status=passed`, 2 persisted `attachment` candidates, both `needs_review` and `source_valid`; review report `object_type=missing_item_candidate` returned 2 items.
- Missing item candidate export smoke result: JSON and HTML review report exports with `object_type=missing_item_candidate`, `needs_review`, and `require_source_valid=true` each created 1 tracked export item; downloads included `missing_item_candidate`.
- Analysis retrieval now strips common short Hungarian accusative suffixes, so terms such as `mellekletet` and `kamerafelvetelt` can fall back to `melleklet` and `kamerafelvetel`.
- The formerly failing short query `Keress hivatkozott mellekletet.` now succeeds in live smoke: `analysis 200`, `validation_status=passed`, 1 source-cited `attachment` candidate.
- Minimal frontend scaffold exists under `frontend/`.
- Frontend currently supports case list/create, TXT import, analysis module run, review report loading/filtering, and JSON/HTML export creation/download.
- Frontend now supports review actions for report items: `verify`, `reject`, `mark_needs_review`, and `comment`.
- Review action calls use a frontend allowlist that maps known object types to their review endpoints; unsupported object types are rejected client-side.
- Frontend report items now show all source references with citation labels, page/chunk hints, quote/excerpt offsets, source excerpts, document hashes, and review history.
- Frontend now shows current operation, elapsed time, last action summary, and analysis output count to make long LM Studio calls less ambiguous.
- Frontend now shows selected-case documents and recent analysis runs; import and analysis execution refresh those lists.
- Frontend document details show imported pages and chunks with source text; analysis run details show recorded inputs/outputs with readable source and object summaries before the raw audit payload.
- Frontend review report controls can filter by object type, review status, and source validation status. Exports use the same selected filters.
- Frontend object detail panel shows object-specific facts, sources, and review history for the selected report item.
- Frontend review report filtering is handled through object type, review status, and source validation dropdown controls.
- Frontend export history lists prior JSON/HTML exports and download links.
- Frontend visible UI text is localized to Hungarian, with backend enum/internal values mapped to Hungarian labels before display.
- Frontend uses Vite proxy from `/api` to `http://127.0.0.1:8000`; backend CORS was not loosened.
- Codex-started Vite must be detached with `setsid`; otherwise a non-interactive WSL shell can close after Vite prints `ready`, leaving `Hangup` in `/tmp/boberdetective-frontend.log` and no `5173` listener. Use:
  `setsid sh -c "npm --prefix frontend run dev -- --host 0.0.0.0 > /tmp/boberdetective-frontend.log 2>&1" < /dev/null &`
  Always confirm with `ss -ltnp | grep 5173` and a Windows-side `curl.exe -I http://localhost:5173`.
- Frontend verification: `npm run build` passed after contradiction claim-pair UI updates.
- End-to-end frontend/API smoke passed through live backend and Vite dev server: case creation, TXT import, document/chunk/search checks, all MVP analysis modules, review report/filter, claim review, JSON export/list/download, frontend index, and Vite `/api` proxy.
- Raw-chunk analysis no longer falls back to first current case chunks when retrieval has no hits; it now returns a clear source-selection error instead of sending unrelated chunks to the LLM.
- Live `extract_claims` module smoke result: `analysis 200`, `validation_status=passed`, 2 persisted claims.
- Live `extract_events` module smoke result: `analysis 200`, `validation_status=passed`, 1 persisted event.
- Keyword search now uses sanitized prefix `to_tsquery` terms so simple Hungarian suffix cases like `kapu` matching `kaput` are less brittle.
- Case review report works through `GET /api/v1/cases/{case_id}/review-report`.
- The review report is read-only and returns combined claim/entity/event items with review status, source validation status, source references, quote text, analysis run id, and review history.
- Review report supports optional query filters: `object_type`, `review_status`, and `source_validation_status`.
- Review report sources now include document filename/SHA256, quote offsets, chunk/page metadata, and bounded source text excerpts for human verification.
- Live review report smoke result: `report 200`, 3 total items, 3 `needs_review`, each with 1 source.
- Entity items are included in review report and JSON/HTML review report exports through their source-linked mentions.
- Live entity report/export smoke result: `report 200`, 2 entity items with sources; HTML export `201`, 2 entity export items.
- JSON review report export works through `POST /api/v1/cases/{case_id}/exports`.
- Export list/detail/download work through `GET /api/v1/cases/{case_id}/exports`, `GET /api/v1/cases/{case_id}/exports/{export_id}`, and `GET /api/v1/cases/{case_id}/exports/{export_id}/download`.
- Export creation writes a JSON file under the case export directory, records SHA256, creates `export_items`, and writes DB + JSONL audit.
- Supported first export request: `export_type=json` or `html`, `export_scope=review_report`, with `review_filter` values `all`, `verified_only`, `needs_review`, `rejected`, `require_source_valid`, and optional `report_filters`.
- Live export smoke result: `export 201`, 3 export items, JSON download `200`, SHA256 recorded.
- HTML review report export works through the same export endpoint with `export_type=html`.
- HTML export escapes item text, body text, citation labels, and quote text before rendering.
- Live HTML export smoke result: `export 201`, 3 export items, `.html` file, download `200`, `text/html`.
- Export review works through `POST /api/v1/cases/{case_id}/exports/{export_id}/reviews`.
- Supported export review actions use the shared human review request shape: `verify`, `reject`, `mark_needs_review`, `comment`.
- Export detail responses now include append-only review history.
- Export review writes `human_reviews` records with `object_type=export` and `export_review_recorded` audit events.
- Live export review smoke result: `review 200`, one review entry, `new_review_status=verified`.
- Storage path traversal protection is covered by tests.
- Live filtered report/export smoke result: `report 200`, entity-only `needs_review` and `source_valid` filter returned 2 items; JSON export `201`, 2 entity export items.
- Latest test run: `186 passed`.

## Suggested Prompt For A New Codex Session

Use this when starting a fresh session:

```text
Read AGENTS.md, AI_NOTES.md, CHANGELOG.md if it exists, and the existing README.md first.

Do not edit anything yet.

After reading them, summarize:
1. what this project does
2. the current architecture
3. the most important constraints
4. the current project state from AI_NOTES.md
5. recent notable changes from CHANGELOG.md, if available
6. the likely next steps
7. which files are most relevant for the task I will give you next

Then wait for my actual task.
```

## Notes For Future Agents

- The user prefers deliberate design before implementation.
- The current emphasis is architecture, runtime, database schema, auditability, and source traceability.
- Do not assume the project should become a chatbot.
- Do not treat LLM output as truth.
- Do not add cloud integrations.
- Do not begin coding unless explicitly asked.
- Keep assumptions and unverified items clearly marked.
- Keep future visible frontend text Hungarian; do not expose raw English enum/internal values directly in the UI unless they are technical identifiers intentionally shown in code/hash/id contexts.
