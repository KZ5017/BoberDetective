# Current State

## Session Handoff Baseline v1

This file is the quick-start handoff for a fresh Codex session.

Read these first:

- `AGENTS.md`
- `README.md`
- `AI_NOTES.md`
- `CHANGELOG.md`
- `CURRENT_STATE.md`

Then run:

```bash
.venv/bin/pytest -q
.venv/bin/alembic current
```

Expected current baseline:

```text
pytest: 98 passed
alembic: 0012_missing_item_candidates (head)
```

## What Works Now

- FastAPI backend scaffold.
- Minimal React/Vite frontend workbench scaffold under `frontend/`.
- PostgreSQL and Qdrant Docker Compose development runtime.
- SQLAlchemy/psycopg database layer.
- Alembic migrations through `0012_missing_item_candidates`.
- Immutable TXT import with page/chunk persistence.
- Keyword search over current page/chunk text.
- Source references with quote validation.
- LM Studio provider abstraction and local model smoke checks.
- Analysis run provenance.
- Source-cited `extract_claims` and `extract_events` modules.
- Source-cited `extract_entities` module.
- Source-cited `summarize_case` module that persists summary items.
- Analysis module service split into common retrieval/JSON helpers and module-specific claim/event/entity/summary services.
- Analysis retrieval fallback strips common Hungarian suffixes, including short accusative forms such as `mellekletet` -> `melleklet`.
- Analysis retrieval falls back to the first current case chunks when keyword search returns no hits, so broad UI prompts can still run against concrete sources.
- Source-cited summary item persistence, API, review workflow, and review report inclusion.
- Contradiction candidate persistence, source linkage, API, review workflow, and review report inclusion.
- `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs.
- Missing item candidate persistence, source linkage, API, review workflow, and review report inclusion.
- `detect_missing_items` analysis module foundation over source-cited chunk quotes.
- Claim, event, source, review, export, and audit persistence.
- Case review report endpoint with object type, review status, source validation filters, and expanded source details.
- JSON and HTML review report export with SHA256, claim/entity/event item tracking, report filters, and expanded source details.
- Missing item candidates are covered by JSON/HTML review report export smoke coverage.
- Frontend build verifies through `cd frontend && npm run build`.
- Frontend review actions work for review report item object types through allowlisted API paths.
- Frontend report items show source details, source excerpts, document hashes, and review history.
- Frontend long-running operation feedback shows current operation, elapsed time, and last action summary.
- Frontend shows document list and analysis run history for the selected case.
- Frontend shows document page/chunk drill-down and analysis run input/output detail.
- Frontend review report supports object type, review status, and source validation filters plus object detail panel.
- Frontend shows export history and focused review queue shortcuts.
- Append-only human review history for claims, entities, events, and exports.
- Shared review helper for claim/entity/event/export review mapping, listing, record creation, and audit writing.

## Current Tables

Current database head has:

```text
users, cases, case_users, audit_events,
documents, document_pages, document_chunks,
source_references,
analysis_runs, analysis_run_inputs, analysis_run_outputs,
claims, claim_sources,
entities, entity_mentions,
events, event_sources,
human_reviews,
exports, export_items,
summary_items, summary_item_sources,
contradiction_candidates, contradiction_candidate_sources,
missing_item_candidates, missing_item_candidate_sources,
alembic_version
```

## Main API Surface

System:

- `GET /api/v1/system/health`
- `GET /api/v1/system/llm/smoke`

Cases and documents:

- `GET /api/v1/cases`
- `POST /api/v1/cases`
- `GET /api/v1/cases/{case_id}/documents`
- `POST /api/v1/cases/{case_id}/documents`
- `GET /api/v1/cases/{case_id}/documents/{document_id}/pages`
- `GET /api/v1/cases/{case_id}/documents/{document_id}/chunks`

Search and sources:

- `POST /api/v1/cases/{case_id}/search/keyword`
- `GET /api/v1/cases/{case_id}/source-references`
- `POST /api/v1/cases/{case_id}/source-references`
- `GET /api/v1/cases/{case_id}/source-references/{source_reference_id}`
- `POST /api/v1/cases/{case_id}/source-references/validate`

Analysis:

- `GET /api/v1/cases/{case_id}/analysis-runs`
- `GET /api/v1/cases/{case_id}/analysis-runs/{analysis_run_id}`
- `POST /api/v1/cases/{case_id}/analysis/source-cited-smoke`
- `POST /api/v1/cases/{case_id}/analysis/modules/extract_claims`
- `POST /api/v1/cases/{case_id}/analysis/modules/extract_events`
- `POST /api/v1/cases/{case_id}/analysis/modules/extract_entities`
- `POST /api/v1/cases/{case_id}/analysis/modules/summarize_case`
- `POST /api/v1/cases/{case_id}/analysis/modules/detect_contradiction_candidates`
- `POST /api/v1/cases/{case_id}/analysis/modules/detect_missing_items`

Reviewable objects:

- `GET /api/v1/cases/{case_id}/claims`
- `GET /api/v1/cases/{case_id}/claims/{claim_id}`
- `POST /api/v1/cases/{case_id}/claims/{claim_id}/reviews`
- `GET /api/v1/cases/{case_id}/events`
- `GET /api/v1/cases/{case_id}/events/{event_id}`
- `POST /api/v1/cases/{case_id}/events/{event_id}/reviews`
- `GET /api/v1/cases/{case_id}/entities`
- `GET /api/v1/cases/{case_id}/entities/{entity_id}`
- `POST /api/v1/cases/{case_id}/entities/{entity_id}/reviews`
- `GET /api/v1/cases/{case_id}/summary-items`
- `POST /api/v1/cases/{case_id}/summary-items`
- `GET /api/v1/cases/{case_id}/summary-items/{summary_item_id}`
- `POST /api/v1/cases/{case_id}/summary-items/{summary_item_id}/reviews`
- `GET /api/v1/cases/{case_id}/contradiction-candidates`
- `POST /api/v1/cases/{case_id}/contradiction-candidates`
- `GET /api/v1/cases/{case_id}/contradiction-candidates/{contradiction_candidate_id}`
- `POST /api/v1/cases/{case_id}/contradiction-candidates/{contradiction_candidate_id}/reviews`
- `GET /api/v1/cases/{case_id}/missing-item-candidates`
- `POST /api/v1/cases/{case_id}/missing-item-candidates`
- `GET /api/v1/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}`
- `POST /api/v1/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/reviews`
- `GET /api/v1/cases/{case_id}/review-report`
  - Optional filters: `object_type`, `review_status`, `source_validation_status`

Exports:

- `GET /api/v1/cases/{case_id}/exports`
- `POST /api/v1/cases/{case_id}/exports`
- `GET /api/v1/cases/{case_id}/exports/{export_id}`
- `GET /api/v1/cases/{case_id}/exports/{export_id}/download`
- `POST /api/v1/cases/{case_id}/exports/{export_id}/reviews`

## Core Constraints

- Fully local-first; do not introduce cloud dependencies.
- The LLM is not the source of truth.
- Mandatory rule: no source -> no claim.
- Every AI-created object must be traceable to concrete documents/pages/chunks and an analysis run.
- Human review is required for meaningful use.
- Do not make autonomous legal, investigative, guilt, suspect, or risk decisions.
- Treat LLM output as untrusted input.
- Keep secure coding practices central: avoid SQL injection, XSS, SSTI, command injection, path traversal, unsafe uploads, and unsafe deserialization.

## Smoke Workflow

For a full live smoke, with LM Studio running and Qwen loaded:

1. Create a case.
2. Import a UTF-8 `.txt` document.
3. Run `extract_claims`.
4. Run `extract_events`.
5. Fetch `/review-report`.
6. Create a JSON or HTML review report export.
7. Download the export.
8. Add an export review.

The latest live smoke completed this path successfully.

Latest frontend/API end-to-end smoke:

- Created a case and imported a UTF-8 TXT document through the live backend.
- Verified document list, chunk list, keyword search, frontend index, and Vite `/api` proxy.
- Ran all MVP modules: `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, `detect_missing_items`, and `detect_contradiction_candidates`.
- Result: 15 review report items, review queue filter returned 15 items, one claim review action succeeded, JSON export/list/download succeeded.
- Smoke case id: `9ace31b5-0729-4b49-8cb4-c989389e70c5`.

Latest `summarize_case` live smoke:

- Initial broad/accented query returned `No chunk retrieval hit for query`.
- Analysis retrieval now derives normalized fallback query variants from natural Hungarian prompts.
- Retried with the original broad query after retrieval improvement.
- Result: `analysis 200`, `validation_status=passed`, 3 summary items, all `needs_review` and `source_valid`.
- Review report with `object_type=summary_item` returned 3 source-cited items.

Latest `detect_contradiction_candidates` live smoke:

- Imported a TXT sample with two source-cited claims about different phone call times.
- `extract_claims` produced 2 claims.
- `detect_contradiction_candidates` returned `analysis 200`, `validation_status=passed`, 1 `time_conflict` candidate.
- Candidate was `needs_review`, `source_valid`, and had two source references.
- Review report with `object_type=contradiction_candidate` returned the candidate with expanded source details.

Latest `detect_missing_items` live smoke:

- Imported a TXT sample with references to a camera recording attachment and separate photo documentation.
- `detect_missing_items` returned `analysis 200`, `validation_status=passed`, 2 `attachment` candidates.
- Candidates were `needs_review`, `source_valid`, and had source references created from validated chunk quotes.
- Review report with `object_type=missing_item_candidate` returned 2 source-cited items with expanded source details.

Latest missing item retrieval/export smoke:

- Created a missing item candidate through `detect_missing_items`.
- JSON review report export with `object_type=missing_item_candidate`, `needs_review`, and `require_source_valid=true` returned 1 tracked export item.
- JSON download contained `missing_item_candidate`.
- HTML review report export returned 1 tracked export item and downloaded as `text/html` with `missing_item_candidate` content.
- Retried the formerly failing short query `Keress hivatkozott mellekletet.` after retrieval suffix tuning.
- Result: `analysis 200`, `validation_status=passed`, 1 source-cited `attachment` candidate.

## Next Logical Steps

Recommended order:

1. Do a frontend UX pass for layout density and empty states.
2. Keep retrieval quality improvements incremental as new real query failures appear.

## Important Local Notes

- WSL sometimes fails parallel file reads with transient service errors. Single WSL commands are more reliable.
- LM Studio native `/api/v1/chat` should use `max_output_tokens`, not `maxTokens`.
- Send `reasoning: "off"` only for Qwen-style reasoning models.
- `POST /api/v1/system/llm/load-chat-model` loads the configured chat model through LM Studio native `/api/v1/models/load`.
- Current preferred LM Studio load profile: `context_length=4096`, `eval_batch_size=4096`, `flash_attention=true`, `offload_kv_cache_to_gpu=true`, `echo_load_config=true`.
- Latest model-load smoke returned `qwen/qwen3.5-9b:2`, `status=loaded`, `load_time_seconds=10.784`, with LM Studio echoing `context_length=4096`, `eval_batch_size=4096`, `parallel=4`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`.
- Keep generated data under the configured data root, not inside the Git repository.
- Frontend dev server proxies `/api` to backend port `8000`.
