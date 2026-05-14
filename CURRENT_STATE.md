# Current State

## Session Handoff Baseline v1

This file is the quick-start handoff for a fresh Codex session.

Read these first:

- `AGENTS.md`
- `README.md`
- `AI_NOTES.md`
- `CHANGELOG.md`
- `CURRENT_STATE.md`
- `Design_documents/10_analysis_batch_processing_plan.md`

Then run:

```bash
.venv/bin/pytest -q
.venv/bin/alembic current
```

Expected current baseline:

```text
pytest: 142 passed
alembic: 0013_processing_runs (head)
```

## What Works Now

- FastAPI backend scaffold.
- Minimal React/Vite frontend workbench scaffold under `frontend/`.
- PostgreSQL and Qdrant Docker Compose development runtime.
- SQLAlchemy/psycopg database layer.
- Alembic migrations through `0013_processing_runs`.
- Immutable TXT import with page/chunk persistence.
- Explicit imported-document processing validation run flow.
- Native-text PDF import foundation with configurable `docling_then_pypdf` parser profile, page/chunk persistence, and `parse_document` analysis run provenance.
- Docling optional dependency is installed in `.venv`; explicit `BOBERDETECTIVE_PDF_PARSER=docling` PDF import smoke passed.
- Explicit Tesseract OCR foundation for PDF documents with rendered page images, OCR page/chunk versioning, and `ocr_document` analysis run provenance.
- Image-only/scanned PDF imports without native text now remain as audit-tracked `review_required` documents so the explicit OCR path can process them.
- OCR captures average Tesseract confidence on a 0..1 scale where available and flags low-confidence OCR pages with `low_ocr_confidence`.
- Document page API returns OCR confidence as a numeric value; Decimal-backed DB values are covered by regression tests.
- Synthetic parser/OCR hardening samples can be regenerated with `scripts/generate_pdf_samples.py` and evaluated with `scripts/evaluate_pdf_samples.py`.
- Default upload limit is 50 MiB via `BOBERDETECTIVE_MAX_UPLOAD_BYTES`; this keeps a guardrail while allowing medium scanned PDF samples.
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
- Analysis batch processing is planned in `Design_documents/10_analysis_batch_processing_plan.md`; the first backend slices now support batch-capable `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, and `detect_missing_items` with shared source selection and chunk batching, while preserving focused query mode.
- Latest live batch analysis smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, and returned `validation_status=passed`.
  - `case` source mode selected 6 chunks across the smoke case, ran 3 batches with `batch_size=2`, and returned `validation_status=passed`.
  - Analysis run inputs include `batch_index`, `batch_count`, `chunk_labels`, `source_label`, and `retrieval_score`.
- Latest live batch `extract_events` smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, and returned `validation_status=passed`.
  - `case` source mode selected 4 chunks, ran 2 batches with `batch_size=2`, and returned `validation_status=passed`.
- Latest live batch `extract_entities` smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, and returned `validation_status=passed`.
  - `case` source mode selected 4 chunks, ran 2 batches with `batch_size=2`, and returned `validation_status=passed`.
  - Case-mode audit check showed 4 chunk inputs, batch indexes `[1, 1, 2, 2]`, and 30 output records.
- Latest live batch `summarize_case` smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, and returned `validation_status=passed`.
  - `case` source mode selected 4 chunks, ran 2 batches with `batch_size=2`, and returned `validation_status=passed`.
  - Summary prompt is stricter than extraction prompts: batch output is capped at 3 summary items and body/title must stay directly supported by `quote_text`.
- Latest live batch `detect_missing_items` smoke passed:
  - `document` source mode selected 5 chunks, ran 3 batches with `batch_size=2`, and returned `validation_status=passed`.
  - `case` source mode selected 4 chunks, ran 2 batches with `batch_size=2`, and returned `validation_status=passed`.
  - Case-mode audit check showed 4 chunk inputs, batch indexes `[1, 1, 2, 2]`, and 20 output records.
- Focused `extract_events` regression checked with query `narrátor Dupin`:
  - Original failure cause was invalid LLM JSON caused by an unescaped double quote inside `quote_text`.
  - Event prompt now asks for short quote excerpts, valid JSON escaping, allowed enum values, and avoiding double-quote-containing excerpts when possible.
  - Batch-all-failed errors now include the first batch failure reason, e.g. `batch_1: LLM returned invalid JSON`.
  - Retest returned `HTTP 200` and `validation_status=passed`.
- Source-cited summary item persistence, API, review workflow, and review report inclusion.
- Contradiction candidate persistence, source linkage, API, review workflow, and review report inclusion.
- `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs.
- `detect_contradiction_candidates` is intentionally claim-based, not raw chunk batch-based: it works on existing `source_valid` claims and records claim selection metadata as analysis run input.
- If fewer than two source-valid claims exist, `detect_contradiction_candidates` now returns `validation_status=warning` with a clear unsupported item instead of a hard backend error or unnecessary LLM call.
- `detect_contradiction_candidates` now builds deterministic backend-selected claim pairs before the LLM call, applies safe pair/fetch limits, optionally filters by meaningful focus terms in claim/source text, and rejects model candidates that reference claim pairs outside the selected pair set.
- Claim-pair selection is audit-visible through analysis run `filter` metadata, including `claim_fetch_limit`, `pair_limit`, `selected_pair_count`, `selected_pairs`, focus terms, and matched/selected claim counts.
- Contradiction candidate validation now deduplicates same claim-pair/type candidates, caps most model-proposed `high` severities to `medium`, and replaces model-written titles/descriptions with conservative, pair-bound, source-claim-based Hungarian text.
- `detect_contradiction_candidates` now supports `claim_review_scope`; the default `reviewable` scope uses source-valid claims with review status `new`, `needs_review`, `verified`, or `corrected`, excluding `rejected`.
- `detect_contradiction_candidates` now requires explicit contradiction qualification from the LLM: `is_contradiction_candidate=true` plus a concrete `conflict_basis`; related/contextual pairs without a concrete conflict basis are rejected or recorded as unsupported items instead of persisted as contradiction candidates.
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
- Frontend document import accepts TXT/PDF files.
- Frontend shows an OCR action for PDF documents that need review or have no extracted pages; OCR completion refreshes document status, pages, chunks, and analysis run history.
- Frontend analysis controls now support source scope for batch-capable `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, and `detect_missing_items`: focused query, selected document, whole case, optional focus text, max source chunks, and batch size.
- Frontend now reflects `detect_contradiction_candidates` as a claim-pair module: the analysis panel shows a claim-pair note, optional focus field, and claim review scope selector, analysis summaries show claim-pair based execution, analysis run details render claim-selection metrics and selected pairs instead of raw JSON, and contradiction report items include a conservative review note.
- Frontend analysis focus text starts empty for every module; module-specific helper text is a placeholder only and is never sent to processing unless the user types actual text.
- Frontend review report supports object type, review status, and source validation filters plus object detail panel.
- Frontend shows export history and focused review queue shortcuts.
- Frontend visible labels are localized to Hungarian, including mapped labels for backend enum/internal values.
- Frontend dev server is configured under `frontend/`; when running, it is available at `http://localhost:5173` and proxies `/api` to `http://127.0.0.1:8000`.
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
- `POST /api/v1/system/llm/load-chat-model`

Cases and documents:

- `GET /api/v1/cases`
- `POST /api/v1/cases`
- `GET /api/v1/cases/{case_id}/documents`
- `POST /api/v1/cases/{case_id}/documents`
- `POST /api/v1/cases/{case_id}/documents/{document_id}/process`
- `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr`
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

Latest document-processing/PDF smoke:

- TXT-backed `/documents/{document_id}/process` returned `succeeded`, `passed`, and `processed`, with document input and page/chunk outputs on the analysis run.
- Native-text PDF import returned `201`, created 1 page and 1 chunk, and recorded a `parse_document` analysis run with `validation_status=passed`.
- PDF parser selection is now abstracted behind `BOBERDETECTIVE_PDF_PARSER`; the default profile prefers Docling when available and falls back to local `pypdf`.
- Explicit Docling API smoke returned `import 201`, `processed`, parser `docling`, and `parse_document` run `passed`.
- PDF hardening smoke with a partially empty native-text PDF returned `review_required` and `parse_document` validation `warning`.
- Image-only PDF hardening now verifies that native parsing reports `no_native_text`, while Tesseract OCR can extract text from a generated scanned-style PDF fixture.
- Sample evaluation covers native-text, good scanned, weak scanned, and mixed empty-page PDFs; weak scanned PDF currently triggers `low_ocr_confidence`.
- Explicit OCR API smoke returned `ocr 200`, document `processed`, run `ocr_document`, validation `passed`, and current page `text_source=ocr`.
- The Docling native-text adapter disables OCR, table structure, and remote services for this profile, but the first Docling run downloaded local model artifacts; offline deployment should pre-cache/pin these artifacts.

## Next Logical Steps

Recommended order:

1. Live-smoke contradiction detection after document/case-scope `extract_claims` on real imported documents, including frontend review report inspection.
2. Refine batch-capable raw-chunk module guardrails and status/error wording from live smoke.
3. Decide whether selected claim-pair details should be exposed in a dedicated contradiction detail view beyond analysis run metadata.

Rationale:

- The current focused query workflow remains valuable, but it should become one source selection mode in a shared pipeline.
- The raw-chunk analysis modules are now batch-capable and live-smoke passed on document/case source modes.
- Contradiction detection is downstream of source-cited claims, so it should remain claim-pair based and preserve `no source -> no claim` through claim/source-reference provenance.

## Important Local Notes

- WSL sometimes fails parallel file reads with transient service errors. Single WSL commands are more reliable.
- In this repository, avoid parallel WSL file reads from Codex; repeated attempts have consistently hit WSL service timeouts. Use sequential shell calls instead.
- `rg` is available in WSL (`ripgrep 14.1.0`) and should be preferred for searches.
- Keep visible frontend text Hungarian. Internal API keys and enum values may remain English, but map them to Hungarian labels before rendering.
- LM Studio native `/api/v1/chat` should use `max_output_tokens`, not `maxTokens`.
- Send `reasoning: "off"` only for Qwen-style reasoning models.
- `POST /api/v1/system/llm/load-chat-model` loads the configured chat model through LM Studio native `/api/v1/models/load`.
- LM Studio native chat calls auto-ensure the configured chat model is loaded before `/api/v1/chat`; if no matching loaded instance is found, the backend loads it once with the configured load profile and then sends the chat request to the loaded instance id.
- Current preferred LM Studio load profile: `context_length=4096`, `eval_batch_size=4096`, `flash_attention=true`, `offload_kv_cache_to_gpu=true`, `echo_load_config=true`.
- Latest model-load smoke returned `qwen/qwen3.5-9b:2`, `status=loaded`, `load_time_seconds=10.784`, with LM Studio echoing `context_length=4096`, `eval_batch_size=4096`, `parallel=4`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`.
- Keep generated data under the configured data root, not inside the Git repository.
- Frontend dev server proxies `/api` to backend port `8000`.
