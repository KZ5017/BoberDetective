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
- `Design_documents/14_work_surface_ui_architecture_plan.md`
- `Design_documents/15_full_document_processing_plan.md`
- `Design_documents/16_large_case_document_storage_and_retrieval_plan.md`
- `Design_documents/17_storage_migration_impact_review.md`
- `Design_documents/18_keyword_search_text_store_migration_plan.md`
- `Design_documents/19_document_taxonomy_retirement_plan.md`
- `Design_documents/20_general_rag_question_answering_plan.md`

Then run:

```bash
.venv/bin/pytest -q
.venv/bin/alembic current
```

Expected current baseline:

```text
pytest: 278 passed
alembic: 0043_document_collections (head)
```

## What Works Now

- FastAPI backend scaffold.
- Minimal React/Vite frontend workbench scaffold under `frontend/`.
- PostgreSQL and Qdrant Docker Compose development runtime.
- SQLAlchemy/psycopg database layer.
- Alembic migrations through `0043_document_collections`.
- Immutable TXT import with page/chunk persistence plus first physical text-store writes.
- Explicit imported-document processing validation run flow.
- Native-text PDF import foundation with configurable `docling_then_pypdf` parser profile, page persistence, and `parse_document` analysis run provenance.
- Native PDF import now has a pre-persistence quality gate: parser results with quality issues such as empty pages do not create current pages, text layers, chunks, or indexing material. The original PDF remains stored for OCR, the document becomes `review_required`, and the analysis run points to `next_action=run_ocr`.
- Clean native PDF parse results now write `document_text_layers` plus `pages.jsonl` in addition to the current DB-backed page rows.
- Current chunking strategy is page-local `char_window_v2`: chunks do not span processed page boundaries, preserve source-location fidelity, and prefer paragraph breaks before sentence-end breaks, line breaks, spaces, and finally hard character limits.
- Docling optional dependency is installed in `.venv`; explicit `BOBERDETECTIVE_PDF_PARSER=docling` PDF import smoke passed.
- Explicit Tesseract OCR foundation for PDF documents with rendered page images, OCR page/chunk versioning, and `ocr_document` analysis run provenance.
- OCR now has a pre-persistence quality decision: clean OCR can create the current text-review layer, partial OCR does not create a text layer automatically and reports usable/failed page numbers, and completely unusable OCR reports `next_action=discard_or_replace_document`.
- Partial OCR acceptance backend slice exists: partial OCR writes non-current staged OCR candidate pages under the data root, and `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr/accept-partial` can explicitly promote selected usable OCR pages into a current `ocr` text-review layer.
- Clean OCR and accepted partial OCR now write `document_text_layers` plus `pages.jsonl`. When OCR replaces an older text layer, previous current text/chunk manifests are marked non-current.
- Document list/detail responses include backend OCR recommendation metadata (`hidden`, `recommended`, `optional`) based on PDF status, current pages/chunks, text density, and empty-page signals; the frontend uses this instead of guessing when to show OCR actions.
- Document page/chunk detail endpoints list only current versions by default, so an OCR run replaces the visible working text layer instead of showing old native and new OCR pages/chunks together. Their API responses still expose `extracted_text` / `chunk_text` for frontend compatibility, but those values are populated from the physical text-store helper, not PostgreSQL text columns.
- Native PDF import and OCR now stop at an explicit text-review layer (`text_review_required`) after creating current pages. Users inspect pages, optionally run OCR, then explicitly create chunks through `POST /api/v1/cases/{case_id}/documents/{document_id}/chunks`; this records a `chunk_document` analysis run and changes the document to `processed` or `review_required` based on validation.
- Image-only/scanned PDF imports without native text now remain as audit-tracked `review_required` documents so the explicit OCR path can process them.
- OCR captures average Tesseract confidence on a 0..1 scale where available and flags low-confidence OCR pages with `low_ocr_confidence`.
- Document page API returns OCR confidence as a numeric value; Decimal-backed DB values are covered by regression tests.
- Synthetic parser/OCR hardening samples can be regenerated with `scripts/generate_pdf_samples.py` and evaluated with `scripts/evaluate_pdf_samples.py`.
- Default upload limit is 50 MiB via `BOBERDETECTIVE_MAX_UPLOAD_BYTES`; this keeps a guardrail while allowing medium scanned PDF samples.
- Keyword search over current page/chunk text.
- Large-case storage migration foundation has started: `document_text_layers` and `document_chunk_manifests` now define durable metadata contracts for future file-backed extracted text and chunk manifests, while the current runtime remains DB-backed.
- `app/services/text_store.py` now contains the DB-backed `SourceTextResolver` plus JSONL page/chunk helper dataclasses and read/write functions with SHA256 manifest hashes. TXT import writes `pages.jsonl` / `chunks.jsonl` plus `document_text_layers` / `document_chunk_manifests`; clean PDF native parsing, clean/accepted OCR, and explicit chunk creation now also write the corresponding text-store manifests.
- Migration `0040_drop_db_text_cols` removes the legacy PostgreSQL full-text storage columns `document_pages.extracted_text` and `document_chunks.chunk_text` plus their old FTS indexes. Full page/chunk text now lives in the data-root text store; PostgreSQL keeps metadata, manifests, search entries, source references, workflow, and audit/provenance data.
- Migration `0041_detach_audit_lifecycle` removes the hard `audit_events.case_id` and `audit_events.analysis_run_id` foreign keys. Audit rows now keep those UUIDs as historical metadata so a full case delete can remove case-owned work data while preserving the audit trail.
- Migration `0042_doc_proc_person_only` removes the unfinished non-person full-document profile path from the database contract: `document_processing_items.profile_key` is limited to `person_search_seeds`, `item_kind` is limited to `person`, and any pre-existing non-person preparatory worklist rows are deleted during upgrade.
- Migration `0043_document_collections` adds the first general RAG/source-scope backend foundation: many-to-many `document_collections` and `document_collection_memberships`, case-insensitive per-case collection names, membership metadata, and active-document source-scope resolution support.
- Iratgyujtemeny backend/API v1 is implemented: collection create/list/update/delete, document add/remove/list, document-to-collections lookup, and `POST /api/v1/cases/{case_id}/document-collections/resolve-scope` for deduplicated active-document source scopes. Collection membership does not duplicate documents and does not alter source validation, review, merge, or object semantics.
- Iratgyujtemeny frontend v1 is implemented inside the `Ügy munkapad` left workflow column: users can create/delete collections, preview a selected collection as source scope, choose an independent target collection in the `Iratok` panel, mark individual or all visible documents, bulk-add marked documents, keep the marked set for adding the same document batch to multiple collections, inspect selected collection contents, search within collection members, and bulk-remove marked documents from a collection.
- Frontend work-surface shell v2 is now active: the old top module selector has been replaced with a left sidebar, shared surface headers show the active case context plus current/last AI operation status, and the separate `Aktuális AI művelet` strip has been retired.
- The left sidebar has been narrowed, model cards are stacked vertically, and each model card keeps a compact two-column internal layout with model name/status on the left and load/unload controls on the right.
- `Irat rendező` is now the default work surface for case selection/creation, import, document list management, document collections, and document detail. Its current layout uses a 1:1 organizer grid: import above the document list on the left, document collections as the full right column, and document details below.
- `Ügy munkapad` is now focused on analysis, research findings, review report, detached sources, and downstream work. Its semantic index readiness/status block and the persistent latest research search summary sit together in a top status row above the analysis/research work area.
- The `Ügy munkapad` desktop layout now treats the analysis/research area as a paired workflow: `Elemzés` and `Kézi ellentmondásjelölt` are stacked in the left column, `Kutatási találatok` fills the right column and scrolls internally instead of stretching the page, and the right column keeps the wider `0.8fr / 1.2fr` split. `Teljes iratfeldolgozás` and the document organizer keep their equal-width column structure. Analysis controls have been compacted into a single settings row where possible, and source-scope helper text uses a shared subdued hint style.
- The `Ügy munkapad` lower panels were reorganized for a full-width readable workflow: `Áttekintési jelentés`, `Találat részletei`, `Leválasztott forráshivatkozások`, and `Elemzési futás részletei` each use full-width rows; `Elemzési előzmények` sits beside the stacked `Export előzmények` / `Export` panels in a 1:1 row; and analysis-run details show source-to-result rows rather than raw technical blocks.
- Analysis run list/detail APIs now expose UI-facing summary metadata: run list items include `display_label` for search focus or manual-created object title, output summaries include source-reference document/page/chunk/quote fields when available, and input source summaries return full chunk text so the frontend can show exactly what was sent into an analysis run.
- The frontend visual language has been softened and stabilized into a CSS token/role foundation in `frontend/src/styles.css`: typography, surface/color/border, spacing/layout, radius, shadow, control-height, and state values are centralized as tokens, and existing component classes share CSS-side role primitives for worklist cards, inner panels, compact surfaces, and meta/status chips. Text roles now include explicit control, hint, option, detail, monospace, and chip-weight tokens, so inputs, helper/error text, searchable-select options, source/detail blocks, and technical text can be tuned without one-off selectors. Global buttons remain flatter with subtle color/border state changes and no hover/active movement. The shared searchable-select now has a stable stacking context, and the analysis source-filter panel allows dropdown overflow so collection/document selectors are not clipped by inner panels.
- A targeted Full HD / 1080p media query is active. It overrides the same token system for denser 1080p use: smaller typography/spacing/control heights, compact sidebar/model controls, unified 1080p button sizing, source/detail quote sizing, searchable-select clear-button alignment, and compact object-fact cards. Keep future 1080p tuning inside this media query and prefer token or role-level overrides over broad per-component fixes.
- Iratgyujtemeny source-scope integration is implemented for the active research workflow: `search_findings` accepts `source_mode=collection` with `collection_id`, resolves the collection to a deduplicated active document set, records `collection_id` in analysis run input parameters, and uses the resolved document set for keyword/semantic/hybrid source selection.
- Chunk indexing and index readiness now support selected collection scopes: `ChunkIndexRequest` and `GET /api/v1/cases/{case_id}/indexes/chunks/status` accept `collection_id`, resolve it through the backend source-scope resolver, and the frontend `Elemzés` panel exposes `Iratgyűjtemény` as a searchable source-scope selector with matching index status and background indexing behavior.
- Full case deletion is available through `DELETE /api/v1/cases/{case_id}` and the frontend `Ügy végleges törlése` action. It deletes case-owned DB rows, requests Qdrant point deletion by `case_id`, removes the case data-root directory, and writes a surviving global `case_deleted` audit event.
- Latest full workflow/delete smoke: user completed two-file import, OCR on both files, chunk creation, indexing, keyword search, hybrid search, and conversion of one finding from each path into structured objects without errors. Frontend full-case delete then removed the case. Post-delete checks found no case-owned DB rows, no case data-root directory, and zero Qdrant points for the deleted case; only intended `audit_events` and the dev user remained.
- First full-document processing backend foundation exists through migration `0039_doc_proc_items`: `document_processing_items` table, `full_document_processing` analysis run type, `document_processing_item` analysis output type, SQLAlchemy model, schemas, profile registry, read/list/status API skeleton, and a first run-start API/service slice.
- The full-document run-start slice reads current document pages from the data-root text store, sends the selected page range to the local chat model in one request, stores valid preparatory `document_processing_items`, and records them as `analysis_run_outputs`. The request has no artificial item cap; it uses a 9000-token output safety ceiling to stop runaway repetition, while long local LLM calls use the configured 900 second timeout.
- Full-document prompt strategy is intentionally compact: the system prompt keeps only source-faithfulness / no outside knowledge / no legal blame / valid JSON constraints, and the user prompt asks only for person worklist seeds with `display_label`, `recommended_search_focus`, and `source_label`. The model is not asked to produce `short_description`, `unsupported_items`, or character-exact quotes in this workflow.
- Full-document processing currently has exactly one active profile: `person_search_seeds`. The earlier planned non-person/entity search profile was removed until it can be redesigned separately with its own prompt and validation contract.
- Full-document source evidence is built by the backend from the returned `display_label` plus `source_label`: the label must be found on the selected source page, matching is tolerant of OCR spacing such as `Pistabá` vs `Pista bá`, and the stored evidence uses the exact original source substring and character span. Repeated exact labels are preserved as worklist candidates and list responses expose `occurrence_status` (`unique` / `repeated`) for the frontend label.
- Full-document person-profile fields are intentionally minimal: the LLM returns `display_label`, `recommended_search_focus`, and `source_label`. The prompt does not ask for `short_description` or model-provided `unsupported_items`; backend validation still records its own `unsupported_items` diagnostics. The backend uses the LLM `recommended_search_focus` when present and falls back to the validated `display_label` only when missing.
- Full-document source-label validation is tolerant of LLM page-label mistakes: the claimed `source_label` is tried first, but if the validated person label is not found there, the backend searches the selected page range and stores the actual page where the label is found. If the label is not present anywhere in the selected source pages, the item is still saved as a normal worklist item with empty `source_evidence_json`, a `Nem megerősített` frontend label/style, and validation metadata recording the LLM-proposed page label and reason.
- The `Teljes iratfeldolgozás` frontend surface is connected to backend profiles, selected-document page-range run-start execution, active/set-aside item list loading, inline source-evidence display, set-aside/restore item status changes, deletion marking, "összes látható törlésre jelölése", bulk soft-delete, display-label search within the worklist, and one-click focus handoff back to the `Ügy munkapad` `search_findings` workflow.
- Runtime reads for source text now go through physical text-store helpers: analysis run previews, review report source excerpts, research finding source excerpts, `search_findings` SOURCE block construction, LLM quote validation, source-reference quote/span validation, source-cited smoke analysis, embedding input, explicit chunk creation, and page/chunk detail API responses no longer depend on DB-stored full text.
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
- Chunk index status endpoint exists at `GET /api/v1/cases/{case_id}/indexes/chunks/status`; it reports current/indexed/missing chunk counts for the configured embedding model, readiness, collection name, latest `embed_chunks` run metadata, and latest run input/output progress. It supports whole-case, selected-document, and explicit document-list scopes. Frontend shows this in a semantic index status panel, disables semantic/hybrid analysis runs when the current source scope is not fully indexed, and displays background indexing progress such as `8/16`.
- Hybrid retrieval foundation exists: `POST /api/v1/cases/{case_id}/search/hybrid` supports `keyword`, `semantic`, and `hybrid` strategies. `search_findings` can receive `retrieval_strategy`, and analysis run chunk inputs record `retrieval_match_type`.
- Configured embedding model defaults to `text-embedding-bge-m3`. Embedding calls auto-ensure the configured embedding model is loaded through LM Studio native `/api/v1/models/load` before calling OpenAI-compatible `/v1/embeddings`. Embedding model loading uses `context_length=4096`; LM Studio currently rejects `eval_batch_size`, `flash_attention`, and `offload_kv_cache_to_gpu` for embedding models, so those are intentionally not sent for embedding load. Chat model loading uses `context_length=61440`, `eval_batch_size=4096`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`.
- Historical Qwen embedding smokes remain useful only as implementation history. The Qwen embedding profile is no longer the active path and should not be restored as the default.
- The current configured embedding default is `text-embedding-bge-m3`; reindexing uses a separate model-specific Qdrant collection, so existing Qwen-backed vectors are not treated as current.
- Current balanced two-model profile: chat `context_length=61440`, chat `eval_batch_size=4096`, BGE-M3 embedding `context_length=4096`, and LLM request timeout `900` seconds for long full-document runs.
- Latest background indexing smoke succeeded against the Morgue PDF: a 16-chunk forced reindex returned immediately with run `603f6b0b-1337-4048-a1c4-139a8f9a049d`, status polling showed `0/16 -> 8/16 -> 16/16`, and the run finished `succeeded` / `passed`.
- Historical focused analysis smokes with the removed raw modules remain useful as test history, but they no longer describe active workflows.
- Regression smoke for the query `elkövető személye` now passes with both `hybrid` and `semantic` retrieval after adding strict JSON repair for claim extraction responses with unescaped quote characters.
- Claim extraction also has deterministic lenient field recovery for malformed `quote_text` values with internal quotes when both the original model response and JSON-repair response are invalid JSON; recovered candidates still require exact quote text in the selected source chunk.
- User-side semantic/hybrid retrieval smoke after switching to the lighter local model profile found the selected sources broadly consistent with the current retrieval design, with no obvious quality regression observed yet. Remaining gaps are expected to be addressed by ranking calibration, broader source-mode integration, and clearer source-selection visibility.
- First hybrid ranking calibration slice is implemented: hybrid source retrieval gives explicit scoring weight to keyword score, semantic score, exact phrase evidence, and keyword/semantic overlap. Source selection now collects candidates across every query variant before applying the final chunk cap, so later keyword/normalized query hits are not starved by the first semantic result set.
- Document and case source modes use retrieval-aware source selection from the required focus text. In document mode, retrieval is constrained to the selected document; in case mode, it can search the whole case.
- Source-selection query variants keep Hungarian accents and accept non-stopword terms from two characters; the original focus text is still the first retrieval query.
- `search_findings` backend source selection still supports optional `page_start` / `page_end` only inside selected-document source scope for API compatibility, but the frontend no longer exposes page-range controls. UI selected-document searches use the full selected document.
- Whole-case finding search has no page-range fields or backend page-range requirement. If API callers omit page fields for selected-document scope, the backend uses the full document and rejects only out-of-document ranges.
- Historical user-side retrieval/analysis smoke after selected-document page-range filtering produced precise results, but the current large-case UI direction favors whole selected-document search because typical documents are expected to be about 30-50 pages.
- Document taxonomy/source-filtering planning exists historically in `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`, but the large-case import/retrieval direction has changed. `Design_documents/19_document_taxonomy_retirement_plan.md` is now the active cleanup record for removing import-time document group/type workflows. Frontend taxonomy workflow cleanup, backend API/filter cleanup, and DB/model/search-entry column removal are implemented. Migration `0037_remove_doc_taxonomy` removes `documents.document_group_code`, `documents.document_type_code`, `document_search_entries.document_group_code`, `document_search_entries.document_type_code`, and the related taxonomy indexes/constraints. Do not build new behavior on document group/type filters.
- Document lifecycle/parking foundation is implemented through migration `0020_document_lifecycle_status`. Documents have `lifecycle_status` values `active`, `excluded`, and `archived`, with status-change metadata and audit events. Active documents are the only source material for new indexing, retrieval, raw-chunk analysis, source-reference creation, manual source-bound object creation, detached-source reattachment, source move/detach/merge operations, and contradiction candidate creation/claim selection. Existing findings from inactive documents remain visible for historical review, and review report sources show the source document lifecycle status.
- Early document discard/delete is available only for safely discardable documents before they become analysis/source material. Once chunks, source references, analysis inputs, or review consequences exist, documents are parked through `excluded` or `archived` instead of being physically removed.
- Frontend source-search strategy selection is available for document/case finding search. `Szovegresz plafon` defaults to 30 and is capped at 50; the same cap is enforced by the backend. `Batch meret` defaults to 1, is backend-validated between 1 and 15, and controls how the selected source chunks are split into LLM calls. Semantic/hybrid index readiness is required before semantic/hybrid retrieval can run. User-side smoke testing confirmed that short concrete focus terms may lose recall in larger batches even when retrieval selected the correct chunk, so the frontend focus helper recommends trying `1-3` for short, concrete focus values. Selected-document page-range controls have been removed from the frontend.
- Analysis batch processing is captured in `Design_documents/10_analysis_batch_processing_plan.md`, but the active raw-source analysis path is now `search_findings`.
- Strategic analysis-model change is captured in `Design_documents/12_source_bound_findings_model_plan.md` and `Design_documents/13_legacy_analysis_module_retirement_plan.md`: the raw chunk-based automatic extraction modules have been retired from active code paths in favor of a source-bound `research_finding` workflow.
- First `research_finding` backend foundation exists through migration `0021_research_findings`: `research_findings` table, SQLAlchemy model, schemas, internal create/list/get service, read-only list/detail API, and analysis-run output summary support.
- Minimal LLM-backed source-bound finding search exists as backend module `search_findings` through migration `0022_search_findings_run_type`. It uses the same focus text, source scope, retrieval strategy, `Szovegresz plafon`, and batch-size source-selection foundation as the raw-chunk modules, but persists source-cited `research_finding` records with non-binding `suggested_type`.
- The active `search_findings` LLM prompt is split cleanly: the Hungarian system prompt holds the task, source-faithfulness, output-field, quote, source-label, and valid-JSON rules; the user prompt contains only dynamic run data (`QUERY`, `BATCH`, `SOURCE`). The expected JSON shape puts `source_label` first in every finding object to reduce local-model omissions.
- The latest `search_findings` run summary is available through `GET /api/v1/cases/{case_id}/research-findings/latest-run-summary`. It reconstructs the latest research run from analysis-run input/output/audit/finding state and reports focus text, source mode, retrieval settings, selected chunk count, saved/corrected/unconfirmed/rejected counts, validation status, and rejection diagnostics.
- The `Ügy munkapad` frontend shows that latest-run summary as a persistent `Utolsó kutatási keresés` status card next to the semantic index status. Findings with an exact or backend-repaired quote are saved as source-valid research-finding worklist items; findings whose quote cannot be repaired are still saved as `source_invalid` / `unconfirmed` worklist items with warning styling and the existing `Nincs érvényes forráshivatkozás` label.
- `search_findings` quote validation is now three-stage: exact quote matches are `source_valid`; non-exact quotes are repaired to `source_valid` when the backend can recover a meaningful exact substring from the claimed source chunk; and unrepaired valid-label findings are persisted as `source_invalid` with unresolved quote spans for human inspection. Repair requires either one recovered quote part of at least 30 normalized characters or at least two recovered quote parts of at least 12 normalized characters each. Saved `source_invalid` findings can still be converted, and the created structured object preserves the invalid-source status where the target model supports it.
- Research finding API responses now include the source chunk/page context for unrepaired `source_invalid` findings even when the invalid LLM quote cannot be located exactly. This lets the frontend show the text region where the model believed the quote belonged, while keeping the finding clearly marked as `Nincs érvényes forráshivatkozás`.
- Converted `source_invalid` structured objects also keep inspection context in the review report: when an invalid quote cannot be located exactly, the report source still exposes the referenced chunk/page text as `source_text_excerpt` while preserving the invalid source-validation label.
- Detached-source reattach now recalculates claim/event/missing-item source validation from the attached source references instead of blindly setting the target object to `source_valid`. If an invalid quote source is detached and reattached, the target remains in the `Nincs érvényes forráshivatkozás` category. Entity review-report source status is also based on mention source-reference validation, not only on the existence of a mention link.
- Detached-source list responses now include source text context for the referenced chunk/page, and the frontend `Leválasztott forráshivatkozások` panel shows it under a `Szövegrész megtekintése` details block before the `Új találat ebből a forráshivatkozásból` form.
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
- `detect_contradiction_candidates` prompting follows the same current prompt discipline as `search_findings`: a Hungarian system prompt holds task/rules/JSON shape, while the user prompt contains only dynamic `QUERY`, `MAX_CANDIDATES`, and selected `CLAIM_PAIRS`.
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
- Detached sources can be reattached from the parked-source panel or permanently deleted from the parked-source worklist; the old `irrelevant/discarded` parked-source state has been removed through migration `0032_delete_discarded_detached_sources`. Source details also support direct move to another same-main-type target object without first parking the source manually. Subtype matching is intentionally not enforced for direct move or reattach.
- Users can select readonly text from document chunks and create source-bound manual claim/entity/event/missing item candidate objects through `manual_entry` provenance runs.
- Users can also attach a manually selected document-chunk quote directly to an existing claim/entity/event/missing item candidate through `POST /api/v1/cases/{case_id}/manual-source-attachments`. The backend validates the source quote, active source document, target object, and exact duplicate attachments before creating the source reference; this workflow intentionally has no user-entered comment field.
- Detached source items can also create new source-bound manual claim/entity/event/missing item candidate objects and then store the created object as their handled target.
- Review report items that are `corrected` or `source_invalid` can be permanently deleted through an explicit backend/frontend action; dependent contradiction candidates are cleaned up so no broken references remain.
- Source-valid, non-corrected review report items can have their title and description edited from the object detail panel through a backend-validated text update endpoint.
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
- Frontend now has a global model-status bar above the case/work-surface area. It checks LM Studio status on page load, groups chat-model and embedding-model load/unload controls next to their model labels, and keeps a labeled `Állapot frissítése` action on the right.
- Frontend AI operation status is shown in a compact strip below the work-surface selector, focused on current/last AI operation, result, and duration; the old `Művelet állapot` panel inside the `Ügy munkapad` was removed.
- Frontend shows document list and analysis run history for the selected case.
- Frontend shows document page/chunk drill-down and analysis run input/output detail; analysis run detail now includes human-readable selected-source summaries with document/page/chunk, retrieval match type/score, batch position, and text preview, plus short output object summaries.
- Frontend document import accepts TXT/PDF files.
- Frontend shows OCR actions from backend recommendation metadata and exposes `Szovegreszek letrehozasa` when a document is in `text_review_required`; chunk creation refreshes document status, chunks, and analysis run history.
- Frontend analysis controls now support the active `search_findings` workflow with selected-document and whole-case source scopes, required focus text, `Szovegresz plafon`, retrieval strategy, and batch size. Selected-document mode searches the full selected document from the UI. The retired raw modules are no longer frontend options.
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
document_text_layers, document_chunk_manifests,
document_search_entries,
source_references,
analysis_runs, analysis_run_inputs, analysis_run_outputs,
claims, claim_sources,
entities, entity_mentions,
events, event_sources,
human_reviews,
exports, export_items,
contradiction_candidates, contradiction_candidate_sources,
missing_item_candidates, missing_item_candidate_sources,
research_findings, document_processing_items, detached_source_items,
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
- `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr/accept-partial`
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

Full-document processing:

- `GET /api/v1/full-document-processing/profiles`
- `POST /api/v1/cases/{case_id}/documents/{document_id}/full-document-processing/runs`
- `GET /api/v1/cases/{case_id}/documents/{document_id}/full-document-processing/items`
- `POST /api/v1/cases/{case_id}/full-document-processing/items/bulk-delete`
- `PATCH /api/v1/cases/{case_id}/full-document-processing/items/{item_id}`

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
- `DELETE /api/v1/cases/{case_id}/detached-source-items/{item_id}`
- `POST /api/v1/cases/{case_id}/detached-source-items/{item_id}/manual-object`
- `POST /api/v1/cases/{case_id}/manual-source-attachments`
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

1. Continue with broad UX/product/backend design for the `Általános iratkérdező` / local RAG question-answering layer now that the first collection-based source-scope layer is usable.
2. Decide the general RAG answer contract: ephemeral answer vs persisted object, source excerpt display, answer history/provenance, and how much source citation is required for the freer Q&A workflow.
3. Add multi-collection source-scope selection only where the RAG/analysis workflow needs it; the current first implementation intentionally supports one selected collection in `search_findings` and indexing.
4. Keep the current source-bound workbench stable while planning the general RAG layer: `search_findings`, research-finding conversion, full-document person seeds, source validation, and contradiction detection should remain strict and auditable.
5. Decide later whether full-document item handoff should create research findings, structured manual objects, prefilled `search_findings` runs, or feed the new general RAG question flow.
6. Expand the new `Audit napló` work surface into the dedicated full audit-log workflow/API/panel backed by `audit_events` after the general RAG source-scope layer is usable.

Rationale:

- Focus text remains valuable and required for analysis runs, while source scope stays cleanly separated as whole-case or selected-document.
- Structured document taxonomy is no longer the preferred large-case source-narrowing workflow. Its frontend workflow, backend API/filter layer, and DB/model/search-entry columns have been retired. Do not build new behavior on document group/type filters.
- Historical document reclassification events may remain in `audit_events`, but the reclassification workflow itself is now a retirement target.
- Document lifecycle is now an active-source gate. Inactive documents must remain historically visible where already cited, but must not become new source material unless restored to `active`.
- The former raw-chunk automatic extraction modules have already been retired from active code paths. Keep cleanup/documentation focused on the current source-bound `search_findings` workflow and the downstream claim-pair contradiction workflow.
- Contradiction detection is downstream of source-cited claims, so it should remain claim-pair based and preserve `no source -> no claim` through claim/source-reference provenance.
- The next major system direction is an `Általános iratkérdező` / local RAG question-answering layer. It should not replace the strict worklist workflows; it should reuse the existing text-store, retrieval, embedding, source-scope, LM Studio, and analysis-run foundations to answer free-form questions over a selected local corpus, while still preserving internal source provenance.
- UI work-surface architecture and the current CSS token/role baseline are captured in `Design_documents/14_work_surface_ui_architecture_plan.md`. The first shell/navigation slice is implemented: the current workbench is available as `Ügy munkapad`, with surfaces for `Teljes iratfeldolgozás` and `Audit napló`.
- The `Teljes iratfeldolgozás` surface is backend-connected: active-document search/selection, processing profile selection, selected-document summary, page-range run-start, last-run validation summary, active/set-aside worklist views, inline source evidence display, restore, repeated-label tags, worklist name search, deletion marking with all-visible selection plus bulk delete, and focus handoff are implemented.
- Full-document processing backend contract is captured in `Design_documents/15_full_document_processing_plan.md`. `document_processing_item` is a separate preparatory work item, not a `research_finding` and not a structured review object. The current backend/frontend slice exposes profile listing, selected page-range run-start execution, item list/status APIs, active/set-aside worklist views, repeated-label occurrence tags, worklist name search, deletion marking with all-visible selection plus bulk delete, and focus handoff into the `Ügy munkapad`.
- Large-case storage/retrieval redesign is captured in `Design_documents/16_large_case_document_storage_and_retrieval_plan.md`. It shifts the next backend target away from DB-centric full page/chunk text storage toward PostgreSQL metadata/workflow/audit, data-root text store for extracted pages/chunks, and Qdrant retrieval indexes.
- The code-level impact map is captured in `Design_documents/17_storage_migration_impact_review.md`. The storage migration is now past the compatibility-fallback phase: `app/services/text_store.py` reads JSONL-backed page/chunk text from the data root, and migration `0040_drop_db_text_cols` removes the old DB text columns.
- `app/services/text_store.py` now supports JSONL-backed text-store reads for the main runtime source-text paths: source-reference validation, `search_findings` prompt/quote validation, vector embedding input, analysis previews, review report excerpts, research-finding excerpts, source-cited smoke, explicit chunk creation from reviewed pages, and page/chunk detail API responses. Migration `0035_text_layer_manifests` adds the text-layer/chunk-manifest metadata contract, imports/chunking write physical text-store manifests, and migration `0040_drop_db_text_cols` removes direct PostgreSQL full-text storage.
- The PostgreSQL full-text-search dependency on page/chunk text columns has been retired. `DocumentSearchEntryModel` and `app/services/lexical_index.py` create page/chunk search-entry rows with metadata plus `tsvector` search representation whenever text-layer and chunk manifests are written. Active keyword search queries `document_search_entries.search_vector`; returned quotes are built from physical text-store reads.
- Document taxonomy retirement is captured in `Design_documents/19_document_taxonomy_retirement_plan.md`. Frontend workflow cleanup, backend API/filter cleanup, and DB/search-entry taxonomy column removal are implemented through migration `0037_remove_doc_taxonomy`.

## Important Local Notes

- WSL sometimes fails parallel file reads with transient service errors. Single WSL commands are more reliable.
- In this repository, avoid parallel WSL file reads from Codex; repeated attempts have consistently hit WSL service timeouts. Use sequential shell calls instead.
- `rg` is available in WSL (`ripgrep 14.1.0`) and should be preferred for searches.
- Keep visible frontend text Hungarian. Internal API keys and enum values may remain English, but map them to Hungarian labels before rendering.
- LM Studio native `/api/v1/chat` should use `max_output_tokens`, not `maxTokens`.
- Send `reasoning: "off"` only for Qwen-style reasoning models.
- `POST /api/v1/system/llm/load-chat-model` loads the configured chat model through LM Studio native `/api/v1/models/load`.
- LM Studio native chat calls auto-ensure the configured chat model is loaded before `/api/v1/chat`; if no matching loaded instance is found, the backend loads it once with the configured load profile and then sends the chat request to the loaded instance id.
- Current preferred chat-model LM Studio load profile: `context_length=61440`, `eval_batch_size=4096`, `flash_attention=true`, `offload_kv_cache_to_gpu=true`, `echo_load_config=true`.
- Current preferred embedding model: `text-embedding-bge-m3`; reindex chunks after switching because model-specific Qdrant collections isolate embeddings by configured model name.
- Keep generated data under the configured data root, not inside the Git repository.
- Frontend dev server proxies `/api` to backend port `8000`.
