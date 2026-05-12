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
- Current verification baseline: `pytest: 86 passed`, `alembic: 0011_contradiction_candidates (head)`.

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
- live `summarize_case` smoke passed with the original broad query after retrieval fallback,
- contradiction candidate persistence, source linkage, API, review workflow, and review report inclusion,
- `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs,
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

## Suggested Next Steps

Likely next steps, in order:

1. Read the handoff docs and design documents.
2. Smoke-test `detect_contradiction_candidates` end-to-end against LM Studio on a sample with conflicting claims.
3. Add missing-item candidate foundation.

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
- Alembic migrations through `0011_contradiction_candidates` are applied.
- `users`, `cases`, `case_users`, `audit_events`, `documents`, `document_pages`, `document_chunks`, `source_references`, `analysis_runs`, `analysis_run_inputs`, `analysis_run_outputs`, `claims`, `claim_sources`, `entities`, `entity_mentions`, `human_reviews`, `events`, `event_sources`, `exports`, `export_items`, `summary_items`, `summary_item_sources`, `contradiction_candidates`, and `contradiction_candidate_sources` tables exist.
- Case create/list API works.
- Case creation writes DB audit event and JSONL audit event.
- Document/page/chunk persistence foundation exists.
- Immutable TXT import works through `POST /api/v1/cases/{case_id}/documents`.
- TXT import stores the original bytes under UUID-based immutable storage paths.
- TXT import creates the first `document_pages` record.
- TXT import creates deterministic `document_chunks` records with `char_window_v1`.
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
- Currently supported module keys: `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, `detect_contradiction_candidates`.
- Analysis module implementation is split across `app/services/analysis_module_common.py`, `analysis_module_claims.py`, `analysis_module_events.py`, `analysis_module_entities.py`, and `analysis_module_summaries.py`; `analysis_modules.py` remains the thin public façade for API and compatibility imports.
- The `extract_claims` module performs keyword chunk retrieval, records query/chunk inputs, calls LM Studio native with the `extract_claims_v1` prompt, validates each returned quote against the labeled source chunk, creates source references, persists claims, records outputs, and finishes the analysis run.
- The `extract_events` module performs keyword chunk retrieval, records query/chunk inputs, calls LM Studio native with the `extract_events_v1` prompt, validates each returned quote against the labeled source chunk, creates source references, persists events/event_sources, records outputs, and finishes the analysis run.
- The `extract_entities` module performs keyword chunk retrieval, records query/chunk inputs, calls LM Studio native with the `extract_entities_v1` prompt, validates each returned mention quote against the labeled source chunk, creates source references, persists entities/entity_mentions, records outputs, and finishes the analysis run.
- The `summarize_case` module performs keyword chunk retrieval, records query/chunk inputs, calls LM Studio native with the `summarize_case_v1` prompt, validates each returned quote against the labeled source chunk, creates source references, persists summary_items/summary_item_sources, records outputs, and finishes the analysis run.
- The `detect_contradiction_candidates` module takes existing source-cited claims, records them as analysis inputs, calls LM Studio native with the `detect_contradiction_candidates_v1` prompt, validates returned claim labels, persists contradiction_candidates/contradiction_candidate_sources, records outputs, and finishes the analysis run.
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
- Latest test run: `86 passed`.

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
