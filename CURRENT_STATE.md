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
- `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`
- `Design_documents/12_source_bound_findings_model_plan.md`
- `Design_documents/13_legacy_analysis_module_retirement_plan.md`

Then run:

```bash
.venv/bin/pytest -q
.venv/bin/alembic current
```

Expected current baseline:

```text
pytest: 220 passed
alembic: 0031_detached_source_claims (head)
```

## What Works Now

- FastAPI backend scaffold.
- Minimal React/Vite frontend workbench scaffold under `frontend/`.
- PostgreSQL and Qdrant Docker Compose development runtime.
- SQLAlchemy/psycopg database layer.
- Alembic migrations through `0031_detached_source_claims`.
- Immutable TXT import with page/chunk persistence.
- Explicit imported-document processing validation run flow.
- Native-text PDF import foundation with configurable `docling_then_pypdf` parser profile, page persistence, and `parse_document` analysis run provenance.
- Current chunking strategy is page-local `char_window_v2`: chunks do not span processed page boundaries, preserve source-location fidelity, and prefer paragraph breaks before sentence-end breaks, line breaks, spaces, and finally hard character limits.
- Docling optional dependency is installed in `.venv`; explicit `BOBERDETECTIVE_PDF_PARSER=docling` PDF import smoke passed.
- Explicit Tesseract OCR foundation for PDF documents with rendered page images, OCR page/chunk versioning, and `ocr_document` analysis run provenance.
- Document list/detail responses include backend OCR recommendation metadata (`hidden`, `recommended`, `optional`) based on PDF status, current pages/chunks, text density, and empty-page signals; the frontend uses this instead of guessing when to show OCR actions.
- Document page/chunk detail endpoints list only current versions by default, so an OCR run replaces the visible working text layer instead of showing old native and new OCR pages/chunks together.
- Native PDF import and OCR now stop at an explicit text-review layer (`text_review_required`) after creating current pages. Users inspect pages, optionally run OCR, then explicitly create chunks through `POST /api/v1/cases/{case_id}/documents/{document_id}/chunks`; this records a `chunk_document` analysis run and changes the document to `processed` or `review_required` based on validation.
- Image-only/scanned PDF imports without native text now remain as audit-tracked `review_required` documents so the explicit OCR path can process them.
- OCR captures average Tesseract confidence on a 0..1 scale where available and flags low-confidence OCR pages with `low_ocr_confidence`.
- Document page API returns OCR confidence as a numeric value; Decimal-backed DB values are covered by regression tests.
- Synthetic parser/OCR hardening samples can be regenerated with `scripts/generate_pdf_samples.py` and evaluated with `scripts/evaluate_pdf_samples.py`.
- Default upload limit is 50 MiB via `BOBERDETECTIVE_MAX_UPLOAD_BYTES`; this keeps a guardrail while allowing medium scanned PDF samples.
- Keyword search over current page/chunk text.
- Source references with quote validation.
- LM Studio provider abstraction and local model smoke checks.
- Analysis run provenance.
- Source-bound `search_findings` analysis module as the main research workflow.
- `detect_contradiction_candidates` remains available as a downstream claim-pair workflow over existing source-valid claims.
- The legacy raw chunk-based automatic extraction modules (`extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, `detect_missing_items`) have been removed from active backend dispatch, frontend module selection, response schemas, module-specific service files, and prompt/validation tests. API calls with these old module keys now return `Unsupported analysis module`.
- Legacy raw module analysis run names have also been retired at DB constraint level through migration `0029_retire_legacy_run_types`: historical raw-module runs are mapped to `retired_analysis_module` with their original run type preserved in `input_parameters.retired_original_run_type`, and the active contradiction module now records `detect_contradiction_candidates` runs instead of the older internal `detect_contradictions` name.
- `summary_item` has been fully removed from the active structured object model through migration `0025_remove_summary_items`: the API/router/service/schema/model, review-report branch, frontend filter labels, review path mapping, output-summary handling, and DB constraints no longer accept it.
- Analysis module service split now keeps common retrieval/JSON helpers, `search_findings`, and the downstream contradiction module.
- Analysis retrieval fallback strips common Hungarian suffixes, including short accusative forms such as `mellekletet` -> `melleklet`.
- Source-bound finding search requires explicit focus text for source selection. The backend no longer silently falls back to first document/case chunks when retrieval finds no matching source; this avoids blind processing on large cases while preserving `no source -> no claim`.
- Local chunk indexing foundation exists: `POST /api/v1/cases/{case_id}/indexes/chunks` creates LM Studio/OpenAI-compatible embeddings for current chunks, upserts them into model-specific Qdrant collections, stores `embedding_provider`, `embedding_model`, `embedding_vector_id`, and `chunk_run_id` on `document_chunks`, and records an `embed_chunks` analysis run. Already indexed chunks are skipped only when the stored embedding model matches the configured embedding model; switching embedding model makes those chunks eligible for reindexing.
- Background chunk indexing exists at `POST /api/v1/cases/{case_id}/indexes/chunks/jobs`; it returns immediately with the `embed_chunks` analysis run id, then processes embeddings through FastAPI `BackgroundTasks`. The frontend now starts this background job and polls index status instead of waiting for the full LM Studio/Qdrant operation in one HTTP request.
- Embedding index creation is hardware-guarded with `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE` defaulting to `8`; chunks are embedded and upserted to Qdrant batch-by-batch instead of one large request, reducing LM Studio timeout/RAM spikes on 32 GB systems.
- Chunk index status endpoint exists at `GET /api/v1/cases/{case_id}/indexes/chunks/status`; it reports current/indexed/missing chunk counts for the configured embedding model, readiness, collection name, latest `embed_chunks` run metadata, and latest run input/output progress. It accepts the same source-subset fields as case-scope indexing/analysis (`document_ids`, `document_group_code`, `document_type_code`) and evaluates readiness for that resolved document set. Frontend shows this in a semantic index status panel, disables semantic/hybrid analysis runs when the current source scope is not fully indexed, and displays background indexing progress such as `8/16`.
- Hybrid retrieval foundation exists: `POST /api/v1/cases/{case_id}/search/hybrid` supports `keyword`, `semantic`, and `hybrid` strategies. `search_findings` can receive `retrieval_strategy`, and analysis run chunk inputs record `retrieval_match_type`.
- Configured embedding model defaults to `text-embedding-qwen3-embedding-4b@q6_k`. Embedding calls auto-ensure the configured embedding model is loaded through LM Studio native `/api/v1/models/load` before calling OpenAI-compatible `/v1/embeddings`. Embedding model loading uses `context_length=12288`; LM Studio currently rejects `eval_batch_size`, `flash_attention`, and `offload_kv_cache_to_gpu` for embedding models, so those are intentionally not sent for embedding load. Chat model loading uses `context_length=12288`, `eval_batch_size=6144`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`.
- Latest Qwen3 8B embedding smoke loaded the embedding model, reindexed 49 chunks from the Morgue PDF into `boberdetective_chunks_text_embedding_qwen3_embedding_8b`, and returned semantic hits through hybrid search. The current configured embedding default is now the smaller `text-embedding-qwen3-embedding-4b@q6_k`; reindexing will use a separate model-specific Qdrant collection.
- Latest local model-load smoke with empty LM Studio state succeeded: `text-embedding-qwen3-embedding-4b` loaded in 3.461s with `context_length=12288`, and `qwen/qwen3.5-9b` loaded in 16.942s with `context_length=12288`, `eval_batch_size=6144`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`.
- Latest 4B embedding reindex smoke succeeded with `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE=8`: 49 Morgue PDF chunks were indexed into `boberdetective_chunks_text_embedding_qwen3_embedding_4b` in about 120s.
- Latest background indexing smoke succeeded against the Morgue PDF: a 16-chunk forced reindex returned immediately with run `603f6b0b-1337-4048-a1c4-139a8f9a049d`, status polling showed `0/16 -> 8/16 -> 16/16`, and the run finished `succeeded` / `passed`.
- Historical focused analysis smokes with the removed raw modules remain useful as test history, but they no longer describe active workflows.
- Regression smoke for the query `elkövető személye` now passes with both `hybrid` and `semantic` retrieval after adding strict JSON repair for claim extraction responses with unescaped quote characters.
- Claim extraction also has deterministic lenient field recovery for malformed `quote_text` values with internal quotes when both the original model response and JSON-repair response are invalid JSON; recovered candidates still require exact quote text in the selected source chunk.
- User-side semantic/hybrid retrieval smoke after switching to the lighter local model profile found the selected sources broadly consistent with the current retrieval design, with no obvious quality regression observed yet. Remaining gaps are expected to be addressed by ranking calibration, broader source-mode integration, and clearer source-selection visibility.
- First hybrid ranking calibration slice is implemented: hybrid source retrieval now gives explicit scoring weight to keyword score, semantic score, exact phrase evidence, and keyword/semantic overlap. This keeps overlap hits from being pushed below purely semantic hits solely because of raw vector score.
- Document and case source modes use retrieval-aware source selection from the required focus text. In document mode, retrieval is constrained to the selected document; in case mode, it can search the whole case.
- Source-selection query variants keep Hungarian accents and accept non-stopword terms from two characters; the original focus text is still the first retrieval query.
- `search_findings` source selection supports a bounded page-range filter (`page_start`, `page_end`) only inside selected-document source scope. The range uses overlap logic (`chunk.page_end >= page_start` and `chunk.page_start <= page_end`) and applies to keyword, semantic, and hybrid retrieval.
- Whole-case finding search has no page-range fields or backend page-range requirement. Selected-document finding search defaults `Oldaltol` to 1 and `Oldalig` to the selected document page count; if API callers omit page fields for document scope, the backend uses the full document and rejects only out-of-document ranges.
- Latest user-side retrieval/analysis smoke after selected-document page-range filtering produced the best and most precise analysis results observed so far; this is a positive quality signal for the combined focus text + source scope + retrieval strategy + page-range workflow.
- Document taxonomy/source-filtering planning exists in `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`. The first backend/frontend/import slices are implemented, backend analysis source selection accepts structured case-scope filters (`document_group_code`, `document_type_code`, `document_ids`), and the frontend analysis panel exposes matching whole-case filters with document group/type dropdowns and a concrete document checkbox list. These filters resolve to a concrete document set and apply consistently to keyword, semantic, hybrid retrieval, semantic/hybrid readiness checks, and background chunk indexing. The old free-text `documents.document_type` column/API field was intentionally removed in migration `0019_drop_legacy_document_type`; structured taxonomy codes are now the only document type/classification path. Documents can be reclassified through audit-tracked metadata-only updates at `PATCH /api/v1/cases/{case_id}/documents/{document_id}/taxonomy`; this changes only `document_group_code` / `document_type_code` and does not touch pages, chunks, source references, analysis runs, or review objects.
- Document lifecycle/parking foundation is implemented through migration `0020_document_lifecycle_status`. Documents have `lifecycle_status` values `active`, `excluded`, and `archived`, with status-change metadata and audit events. Active documents are the only source material for new indexing, retrieval, raw-chunk analysis, source-reference creation, manual source-bound object creation, detached-source reattachment, source move/detach/merge operations, and contradiction candidate creation/claim selection. Existing findings from inactive documents remain visible for historical review, and review report sources show the source document lifecycle status.
- Early document discard/delete is available only for safely discardable documents before they become analysis/source material. Once chunks, source references, analysis inputs, or review consequences exist, documents are parked through `excluded` or `archived` instead of being physically removed.
- Frontend source-search strategy selection is available for document/case finding search. `Szovegresz plafon` defaults to 30 and is capped at 50; the same cap is enforced by the backend. `Batch meret` controls how the selected source chunks are split into LLM calls. Semantic/hybrid index readiness is required before semantic/hybrid retrieval can run.
- Analysis batch processing is captured in `Design_documents/10_analysis_batch_processing_plan.md`, but the active raw-source analysis path is now `search_findings`.
- Strategic analysis-model change is captured in `Design_documents/12_source_bound_findings_model_plan.md` and `Design_documents/13_legacy_analysis_module_retirement_plan.md`: the raw chunk-based automatic extraction modules have been retired from active code paths in favor of a source-bound `research_finding` workflow.
- First `research_finding` backend foundation exists through migration `0021_research_findings`: `research_findings` table, SQLAlchemy model, schemas, internal create/list/get service, read-only list/detail API, and analysis-run output summary support.
- Minimal LLM-backed source-bound finding search exists as backend module `search_findings` through migration `0022_search_findings_run_type`. It uses the same focus text, source scope, retrieval strategy, `Szovegresz plafon`, and batch-size source-selection foundation as the raw-chunk modules, but persists source-cited `research_finding` records with non-binding `suggested_type`.
- First frontend workflow for research findings exists: the analysis module selector exposes `Kutatási találatok keresése`, runs through the normal source-scope/retrieval controls, refreshes `research_findings`, and shows a `Kutatási találatok` panel above the `Áttekintési jelentés` panel with type suggestion, relevance reason, source validation/worklist status, and the source-reference quote.
- Human-controlled `research_finding` conversion exists: `POST /api/v1/cases/{case_id}/research-findings/{finding_id}/convert` reuses the finding source reference, creates a structured claim/entity/event/missing item candidate through the manual-entry path, records a `manual_entry` provenance run plus `research_finding_converted` audit event, and marks the finding as `converted` with `target_object_type` / `target_object_id`. Converted findings no longer appear in the active research-finding worklist; the structured object carries the ongoing review/source workflow.
- Research findings are now explicit worklist items through migration `0024_research_findings_worklist`, not human-review objects. The `research_findings.review_status` column and `research_finding` human-review object type were removed. Worklist operations are `set-aside`, `restore`, single delete, and bulk delete; `ignored` means "félretéve", not rejected. The frontend exposes `Félreteszem`, `Vissza az aktív listába`, `Törlésre jelölés`, and `Jelöltek törlése`.
- The planned `research_finding` model should remain graph-view compatible: preserve source-reference -> finding -> structured-object relationships so a later graph visualization can be built without redesigning the core data model. This is a schema/design constraint, not a near-term graph database requirement.
- Historical raw-module live smokes are pre-retirement notes only. Current live smokes should use `search_findings`, research-finding conversion, manual source-bound object creation, and downstream `detect_contradiction_candidates`.
- Contradiction candidate persistence, source linkage, API, review workflow, and review report inclusion.
- `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs.
- `detect_contradiction_candidates` is intentionally claim-based, not raw chunk batch-based: it works on existing `source_valid` claims and records claim selection metadata as analysis run input.
- Manual contradiction candidate creation now exists as a separate claim-pair workflow: the UI lets the user select two source-valid, non-rejected claims, previews their readonly text and sources, and creates a `needs_review` contradiction candidate through a `manual_entry` provenance run.
- If fewer than two source-valid claims exist, `detect_contradiction_candidates` now returns `validation_status=warning` with a clear unsupported item instead of a hard backend error or unnecessary LLM call.
- `detect_contradiction_candidates` now builds deterministic backend-selected claim pairs before the LLM call, applies safe pair/fetch limits, optionally filters by meaningful focus terms in claim/source text, and rejects model candidates that reference claim pairs outside the selected pair set.
- `detect_contradiction_candidates` now requires focus text. It uses `contradiction_candidate_limit` for its candidate cap, while raw-chunk modules use `max_chunks`. Its focus filter works on already extracted claim text/source quotes, keeps Hungarian accents, and accepts non-stopword terms from two characters.
- Claim-pair selection is audit-visible through analysis run `filter` metadata, including `claim_fetch_limit`, `pair_limit`, `selected_pair_count`, `selected_pairs`, focus terms, and matched/selected claim counts.
- Contradiction candidate validation now deduplicates same claim-pair/type candidates, caps most model-proposed `high` severities to `medium`, and replaces model-written titles/descriptions with conservative, pair-bound, source-claim-based Hungarian text.
- `detect_contradiction_candidates` now supports `claim_review_scope`; the default `reviewable` scope uses source-valid claims with review status `new`, `needs_review`, `verified`, or `corrected`, excluding `rejected`.
- `detect_contradiction_candidates` now requires explicit contradiction qualification from the LLM: `is_contradiction_candidate=true` plus a concrete `conflict_basis`; related/contextual pairs without a concrete conflict basis are rejected or recorded as unsupported items instead of persisted as contradiction candidates.
- Analysis modules now perform historical deduplication before persistence for currently supported structured review objects instead of creating duplicate review objects.
- Entity extraction automatically merges only exact/normalized repeated entities into the existing entity review object and links additional occurrences as mentions/sources.
- Ambiguous entity identity decisions should be handled through the explicit entity merge workflow, not by automatic alias guessing.
- Claim, entity, event, and missing item candidate merge are available from report item cards and the object detail panel where applicable. Merge remains constrained to the same main object type, but subtype matching is intentionally not enforced; source objects are marked `corrected`, sources move to the selected target, and duplicate source links are skipped.
- Claim, entity, event, and missing item candidate source links can be manually detached through audit-tracked `detach_source` review actions; the UI exposes `Levalasztas` on source details where the backend has a concrete source-link id.
- Detached source links are parked in `detached_source_items` with the source reference plus a snapshot of the object they were detached from; the frontend shows these under `Levalasztott forrasok`. Detached source items may originate from claims as well as entities/events/missing item candidates.
- Detached sources can be reattached from the parked-source panel or marked irrelevant; source details also support direct move to another same-main-type target object without first parking the source manually. Subtype matching is intentionally not enforced for direct move or reattach.
- Users can select readonly text from document chunks and create source-bound manual claim/entity/event/missing item candidate objects through `manual_entry` provenance runs.
- Detached source items can also create new source-bound manual claim/entity/event/missing item candidate objects and then store the created object as their handled target.
- Missing item candidate persistence, source linkage, API, review workflow, and review report inclusion.
- Missing item candidates remain supported as structured review objects through manual/finding-conversion workflows; the raw `detect_missing_items` analysis module has been retired.
- Claim, event, source, review, export, and audit persistence.
- Case review report endpoint with object type, review status, source validation filters, and expanded source details.
- JSON and HTML review report export with SHA256, claim/entity/event item tracking, report filters, and expanded source details.
- Missing item candidates are covered by JSON/HTML review report export smoke coverage.
- Frontend build verifies through `cd frontend && npm run build`.
- Frontend review actions work for review report item object types through allowlisted API paths.
- Frontend report items show source details, source excerpts, document hashes, and review history.
- Frontend long-running operation feedback shows current operation, elapsed time, and last action summary.
- Frontend shows document list and analysis run history for the selected case.
- Frontend shows document page/chunk drill-down and analysis run input/output detail; analysis run detail now includes human-readable selected-source summaries with document/page/chunk, retrieval match type/score, batch position, and text preview, plus short output object summaries.
- Frontend document import accepts TXT/PDF files.
- Frontend shows OCR actions from backend recommendation metadata and exposes `Szovegreszek letrehozasa` when a document is in `text_review_required`; chunk creation refreshes document status, chunks, and analysis run history.
- Frontend analysis controls now support the active `search_findings` workflow with selected-document and whole-case source scopes, selected-document page range, required focus text, `Szovegresz plafon`, retrieval strategy, and batch size. The retired raw modules are no longer frontend options.
- Frontend now reflects `detect_contradiction_candidates` as a claim-pair module: the analysis panel shows a claim-pair note, required focus field, claim review scope selector, and contradiction candidate cap, analysis summaries show claim-pair based execution, analysis run details render claim-selection metrics and selected pairs instead of raw JSON, and contradiction report items include a conservative review note.
- Frontend analysis focus text starts empty for every module; module-specific helper text is a placeholder only and is never sent to processing unless the user types actual text.
- Frontend review report supports object type, review status, and source validation filters plus object detail panel.
- Frontend shows export history; review report filtering is handled through object/review/source dropdown filters.
- Frontend visible labels are localized to Hungarian, including mapped labels for backend enum/internal values.
- Frontend dev server is configured under `frontend/`; when running, it is available at `http://localhost:5173` and proxies `/api` to `http://127.0.0.1:8000`.
- Codex background-start caveat: starting Vite via a plain backgrounded WSL shell command can log `ready` and then exit with `Hangup` when the shell is cleaned up. For a persistent Codex-started frontend, use:
  `setsid sh -c "npm --prefix frontend run dev -- --host 0.0.0.0 > /tmp/boberdetective-frontend.log 2>&1" < /dev/null &`
  Verify with `ss -ltnp | grep 5173` or `sudo netstat -lntup`; the frontend should appear as `node` listening on `0.0.0.0:5173`.
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
contradiction_candidates, contradiction_candidate_sources,
missing_item_candidates, missing_item_candidate_sources,
research_findings, detached_source_items,
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
- `POST /api/v1/cases/{case_id}/documents/{document_id}/chunks`
- `POST /api/v1/cases/{case_id}/documents/{document_id}/exclude`
- `POST /api/v1/cases/{case_id}/documents/{document_id}/archive`
- `POST /api/v1/cases/{case_id}/documents/{document_id}/restore`
- `DELETE /api/v1/cases/{case_id}/documents/{document_id}`
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
- `POST /api/v1/cases/{case_id}/analysis/modules/detect_contradiction_candidates`
- `POST /api/v1/cases/{case_id}/analysis/modules/search_findings`
- Legacy raw module keys (`extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, `detect_missing_items`) intentionally return `Unsupported analysis module`.

Reviewable objects:

- `GET /api/v1/cases/{case_id}/claims`
- `GET /api/v1/cases/{case_id}/claims/{claim_id}`
- `POST /api/v1/cases/{case_id}/claims/{claim_id}/reviews`
- `POST /api/v1/cases/{case_id}/claims/{claim_id}/merge`
- `POST /api/v1/cases/{case_id}/claims/{claim_id}/sources/{claim_source_id}/detach`
- `POST /api/v1/cases/{case_id}/claims/{claim_id}/sources/{claim_source_id}/move`
- `GET /api/v1/cases/{case_id}/events`
- `GET /api/v1/cases/{case_id}/events/{event_id}`
- `POST /api/v1/cases/{case_id}/events/{event_id}/reviews`
- `POST /api/v1/cases/{case_id}/events/{event_id}/merge`
- `POST /api/v1/cases/{case_id}/events/{event_id}/sources/{event_source_id}/detach`
- `POST /api/v1/cases/{case_id}/events/{event_id}/sources/{event_source_id}/move`
- `GET /api/v1/cases/{case_id}/entities`
- `GET /api/v1/cases/{case_id}/entities/{entity_id}`
- `POST /api/v1/cases/{case_id}/entities/{entity_id}/reviews`
- `POST /api/v1/cases/{case_id}/entities/{entity_id}/merge`
- `POST /api/v1/cases/{case_id}/entities/{entity_id}/mentions/{mention_id}/detach`
- `POST /api/v1/cases/{case_id}/entities/{entity_id}/mentions/{mention_id}/move`
- `GET /api/v1/cases/{case_id}/contradiction-candidates`
- `POST /api/v1/cases/{case_id}/contradiction-candidates`
- `GET /api/v1/cases/{case_id}/contradiction-candidates/{contradiction_candidate_id}`
- `POST /api/v1/cases/{case_id}/contradiction-candidates/{contradiction_candidate_id}/reviews`
- `GET /api/v1/cases/{case_id}/missing-item-candidates`
- `POST /api/v1/cases/{case_id}/missing-item-candidates`
- `GET /api/v1/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}`
- `POST /api/v1/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/reviews`
- `POST /api/v1/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/merge`
- `POST /api/v1/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/sources/{source_link_id}/detach`
- `POST /api/v1/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/sources/{source_link_id}/move`
- `GET /api/v1/cases/{case_id}/research-findings`
- `GET /api/v1/cases/{case_id}/research-findings/{finding_id}`
- `POST /api/v1/cases/{case_id}/research-findings/{finding_id}/convert`
- `POST /api/v1/cases/{case_id}/research-findings/{finding_id}/set-aside`
- `POST /api/v1/cases/{case_id}/research-findings/{finding_id}/restore`
- `DELETE /api/v1/cases/{case_id}/research-findings/{finding_id}`
- `POST /api/v1/cases/{case_id}/research-findings/bulk-delete`
- `GET /api/v1/cases/{case_id}/detached-source-items`
- `POST /api/v1/cases/{case_id}/detached-source-items/{item_id}/attach`
- `POST /api/v1/cases/{case_id}/detached-source-items/{item_id}/discard`
- `POST /api/v1/cases/{case_id}/detached-source-items/{item_id}/manual-object`
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
3. Run `search_findings`.
4. Convert at least one research finding into a structured object.
5. Fetch `/review-report`.
6. Create a JSON or HTML review report export.
7. Download the export.
8. Add an export review.

The latest live smoke completed this path successfully.

Latest frontend/API end-to-end smoke:

- Created a case and imported a UTF-8 TXT document through the live backend.
- Verified document list, chunk list, keyword search, frontend index, and Vite `/api` proxy.
- Historical note: earlier frontend/API smoke ran the former MVP raw modules before their retirement. Current smokes should use `search_findings`, manual conversion, and `detect_contradiction_candidates`.
- Result: 15 review report items, review queue filter returned 15 items, one claim review action succeeded, JSON export/list/download succeeded.
- Smoke case id: `9ace31b5-0729-4b49-8cb4-c989389e70c5`.

Historical `summarize_case` smokes are no longer active baseline material. The module and `summary_item` object model have been removed from current operation.

Historical `detect_contradiction_candidates` live smoke:

- Imported a TXT sample with two source-cited claims about different phone call times.
- Historical raw `extract_claims` produced 2 claims. Current smokes should create claims through finding conversion or manual source-bound object creation.
- `detect_contradiction_candidates` returned `analysis 200`, `validation_status=passed`, 1 `time_conflict` candidate.
- Candidate was `needs_review`, `source_valid`, and had two source references.
- Review report with `object_type=contradiction_candidate` returned the candidate with expanded source details.

Historical missing item retrieval/export smoke:

- Created a missing item candidate through the former raw `detect_missing_items` path.
- JSON review report export with `object_type=missing_item_candidate`, `needs_review`, and `require_source_valid=true` returned 1 tracked export item.
- JSON download contained `missing_item_candidate`.
- HTML review report export returned 1 tracked export item and downloaded as `text/html` with `missing_item_candidate` content.
- Retried the formerly failing short query `Keress hivatkozott mellekletet.` after retrieval suffix tuning.
- Result: `analysis 200`, `validation_status=passed`, 1 source-cited `attachment` candidate. This remains test history only; the raw module is no longer active.

Latest document-processing/PDF smoke:

- TXT-backed `/documents/{document_id}/process` returned `succeeded`, `passed`, and `processed`, with document input and page/chunk outputs on the analysis run.
- Native-text PDF import now returns current pages and `text_review_required`; explicit chunk creation records a separate `chunk_document` analysis run.
- PDF parser selection is now abstracted behind `BOBERDETECTIVE_PDF_PARSER`; the default profile prefers Docling when available and falls back to local `pypdf`.
- Explicit Docling API smoke returned `import 201`, `processed`, parser `docling`, and `parse_document` run `passed`.
- PDF hardening smoke with a partially empty native-text PDF returned `review_required` and `parse_document` validation `warning`.
- Image-only PDF hardening now verifies that native parsing reports `no_native_text`, while Tesseract OCR can extract text from a generated scanned-style PDF fixture.
- Sample evaluation covers native-text, good scanned, weak scanned, and mixed empty-page PDFs; weak scanned PDF currently triggers `low_ocr_confidence`.
- Explicit OCR API smoke returned `ocr 200`, document `processed`, run `ocr_document`, validation `passed`, and current page `text_source=ocr`.
- The Docling native-text adapter disables OCR, table structure, and remote services for this profile, but the first Docling run downloaded local model artifacts; offline deployment should pre-cache/pin these artifacts.

## Next Logical Steps

Recommended order:

1. Finish documentation cleanup around the retired raw module workflow: older design/status documents may keep historical notes, but active capability lists should point to `search_findings`.
2. Keep hardening `search_findings` as the main source-bound research workflow and preserve the research finding worklist -> structured object conversion path.
3. Design and implement a full `Audit naplo` workflow/API/panel backed by `audit_events`. Keep it conceptually separate from the current `Elemzesi elozmenyek` panel, which lists `analysis_runs`, not all audit events.

Rationale:

- Focus text remains valuable and required for analysis runs, while source scope stays cleanly separated as whole-case or selected-document.
- Structured document taxonomy is now the preferred foundation for large-case source narrowing; do not build new filtering behavior on free-text document type values.
- Document reclassification is intentionally audit-only plus metadata-only; the next audit-log UI should surface `document_reclassified` events and their optional comments from `audit_events`.
- Document lifecycle is now an active-source gate. Inactive documents must remain historically visible where already cited, but must not become new source material unless restored to `active`.
- The raw-chunk analysis modules are batch-capable and live-smoke passed on document/case source modes, but recent user-side quality testing showed the module-first extraction model is too rigid for the local Hungarian LLM workflow. Treat them as retirement candidates, not as the future main workflow.
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
- Current preferred chat-model LM Studio load profile: `context_length=12288`, `eval_batch_size=6144`, `flash_attention=true`, `offload_kv_cache_to_gpu=true`, `echo_load_config=true`.
- Current preferred embedding model: `text-embedding-qwen3-embedding-4b@q6_k`; reindex chunks after switching because model-specific Qdrant collections isolate embeddings by configured model name.
- Keep generated data under the configured data root, not inside the Git repository.
- Frontend dev server proxies `/api` to backend port `8000`.
