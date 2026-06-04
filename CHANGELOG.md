# CHANGELOG.md

## 2026-06-05

### Added

- Added frontend-oriented analysis-run summary metadata: analysis run list items now expose `display_label`, using the `search_findings` query for research runs and the created object title for `manual_entry` runs.
- Expanded analysis run output summaries with source-reference document/page/chunk/quote metadata when available, so the frontend can render source-to-result rows without depending on raw IDs or nested technical payloads.
- Added readable empty/unavailable states to the analysis-run details view for outputs that no longer exist, for example after related findings or review objects have been deleted.

### Changed

- Reworked the `Ügy munkapad` layout: `Áttekintési jelentés`, `Találat részletei`, `Leválasztott forráshivatkozások`, and `Elemzési futás részletei` are full-width rows; `Elemzés` and `Kézi ellentmondásjelölt` are stacked in the left column; `Kutatási találatok` fills the right column and scrolls internally.
- Reorganized the lower workbench row so `Elemzési előzmények` sits beside stacked `Export előzmények` and `Export` panels in a 1:1 layout.
- Split `Elemzési előzmények` into `Kutatási találatok keresése` and `Kézi rögzítés` views, highlighted the selected run card, and showed the research focus or manually created object title directly on each card when available.
- Reworked `Elemzési futás részletei` into a human-readable source-to-result flow: source cards show the full source text sent into the run, result cards omit duplicated nested source-reference noise, and `manual_entry` runs render the selected source next to the object created or attached from it.
- Moved the `Kézi jelölt létrehozása` action to the bottom of the `Kézi ellentmondásjelölt` panel and made it full width, leaving the two claim selectors more horizontal space.

### Verified

- `.venv/bin/pytest -q` (`278 passed`, 1 Docling deprecation warning)
- `npm --prefix frontend run build`
- `git diff --check`

## 2026-06-03

### Added

- Added `GET /api/v1/cases/{case_id}/research-findings/latest-run-summary`, returning the latest `search_findings` run summary for a case with focus text, source mode, retrieval settings, selected chunk count, saved/corrected/unconfirmed/rejected counts, and validation/rejection diagnostics.
- Added a persistent `Utolsó kutatási keresés` frontend status card for the `Ügy munkapad`, backed by the new latest-run summary endpoint instead of transient local state.

### Changed

- Moved the `Utolsó kutatási keresés` card out of the `Kutatási találatok` panel into the same top status row as `Szemantikus index állapot`.
- Adjusted the `Ügy munkapad` grid so `Elemzés` and `Kutatási találatok` use a `0.8fr / 1.2fr` desktop split, giving more width to the research-finding worklist without affecting other work surfaces.
- Reduced the left sidebar width, kept the model cards stacked vertically, and made the model-card internals two-column: model name/status on the left and model actions on the right.
- Removed the old bottom analysis-run summary block from the `Elemzés` panel because the latest-run and research-finding panels now carry the useful state.
- Refined global UI typography toward a calmer visual weight: document names, panel/card titles, status chips, guide text, error text, dropdown values, full-document worklist card titles/focus/source labels, analysis-run detail labels, and research/review card titles now use lighter font weights.
- Reworked global button styling from heavy gradient/inset buttons to flatter, quieter buttons with subtle color/border/box-shadow state changes and no hover/active movement.
- Kept the Full HD media query active as a targeted 1080p layer, currently limited to slightly smaller/lighter buttons, input labels/values, and status-chip weights.
- Simplified the semantic index readiness card: the Qdrant collection name now appears in the first metadata line, and readiness metrics can wrap over multiple lines instead of clipping.

### Verified

- `npm --prefix frontend run build`
- `git diff --check`

## 2026-06-02

### Changed

- Reworked the frontend work-surface shell into a left-sidebar layout with shared surface headers that show the active case context and current/last AI operation state.
- Added `Irat rendező` as the default work surface and moved case selection/creation, import, document list management, document collections, and document detail workflows into it.
- Narrowed `Ügy munkapad` to analysis, research findings, review report, detached sources, and downstream case-work workflows.
- Moved semantic index readiness/status out of the dynamic `Elemzés` panel into a compact fixed-height strip above the analysis controls, while allowing the `Kutatási találatok` column to start at the top of the workbench.
- Standardized two-column work areas in `Ügy munkapad`, `Teljes iratfeldolgozás`, and the document organizer to equal 1:1 columns.
- Compactified the analysis settings row and unified source-scope helper text styling.
- Updated `Design_documents/14_work_surface_ui_architecture_plan.md` to record the current sidebar/surface direction and the role of the new document organizer surface.

## 2026-05-30

### Changed

- Implemented the first backend/API slice of `iratgyujtemeny` / source-scope selection through migration `0043_document_collections`: many-to-many document collections, collection membership metadata, case-insensitive per-case names, and active-document scope resolution.
- Added `app/api/v1/document_collections.py`, Pydantic schemas, service logic, and backend tests for collection CRUD, bulk add/remove semantics, document-to-collection lookup, and deduplicated source-scope previews.
- Added the first frontend `Iratgyűjtemények` slice to the `Ügy munkapad`: create/delete collections, select a collection, add/remove documents from the document list, refresh membership contents, and preview the resolved active-document source scope.
- Improved the document-collection UX for larger document sets: the `Iratok` panel now has its own searchable target-collection selector, per-document marking, all-visible marking, clear selection, and bulk add of marked documents while preserving the marked batch for reuse across multiple collections.
- Added collection-content management to the `Iratgyűjtemények` panel: users can inspect a selected collection's documents, search within them, mark individual or all visible entries, and bulk-remove marked documents from the collection.
- Wired `iratgyűjtemény` into the active research/indexing workflow: `search_findings` supports `source_mode=collection` with `collection_id`, semantic/hybrid index readiness and background indexing accept collection scopes, and the frontend `Elemzés` panel exposes `Iratgyűjtemény` through the shared searchable selector.
- Updated the verification baseline to `278 passed` and Alembic head `0043_document_collections`.
- Reverted the configured LM Studio chat-model load profile to `context_length=61440`, with `eval_batch_size=4096`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`; embedding remains `text-embedding-bge-m3` with `context_length=4096`.
- Hardened the full-document processing runtime for long local model calls: selected page ranges are sent in one LLM request, artificial item caps were removed, the long-call timeout remains 900 seconds, and a 9000-token output safety ceiling is used to stop runaway repeated JSON.
- Simplified the full-document processing prompt: the system prompt keeps only the source-faithfulness and valid-JSON constraints, while the user prompt asks only for person worklist seeds with `display_label`, `recommended_search_focus`, and `source_label`. The model is no longer asked to generate `short_description`, `unsupported_items`, or character-exact source quotes for this workflow.
- Moved full-document source-evidence construction back to the backend: returned `display_label` values are matched against the selected source page, including OCR-spacing tolerant variants such as `Pistabá` / `Pista bá`, and the stored evidence uses the exact original source substring and character span.
- Repeated full-document worklist labels are now preserved instead of discarded; list responses expose `occurrence_status` so the frontend can show `Egyedi` or `Többször előforduló`.
- Removed the unfinished `entity_search_seeds` full-document profile from active backend/frontend workflow and narrowed `document_processing_items` constraints to the stable person profile through migration `0042_doc_proc_person_only`.
- Restored `recommended_search_focus` as an explicit LLM-provided person-profile field and removed unused `short_description` generation from the prompt/backend handoff. The backend uses the returned focus when present and falls back to the validated display label only when it is missing.
- Changed full-document validation so labels that cannot be found on the selected source pages are no longer discarded. They are saved as normal preparatory worklist items with empty source evidence, warning metadata, `Nem megerősített` frontend styling, and the same focus/set-aside/delete workflow as confirmed items.
- Made full-document source evidence tolerant of wrong LLM page labels by searching the selected source pages for the validated label and storing the actual matching page when the returned `source_label` is wrong.
- Rewrote the `search_findings` user prompt from the long English `TASK` rule block into one Hungarian `Feladat és Szabályok` block that frames QUERY as the Hungarian text to search for, requires literal full-query use, and rejects synonym-, assumption-, and inference-based QUERY matching.
- Added an `Azonosítási szabály` block to the `search_findings` prompt so a person/role QUERY is treated as one search unit and partial words are not enough to match another person or similar role.
- Added prompt gates for `search_findings` to reject items when only one separate QUERY word matches or when the model's own `relevance_reason` says the full QUERY does not meet the finding criteria, and added quote-text rules requiring the identifying QUERY connection to appear in the quote.
- Changed the `search_findings` system prompt from generic research-finding extraction to query-bound extraction: QUERY is now declared a strict selection filter, partial word/shared-name/similar-role matches are insufficient, and empty findings are required when no valid QUERY-bound finding exists.
- Reworked `search_findings` prompting into a stable Hungarian system prompt plus dynamic-only user prompt. The system prompt now holds the task, source-faithfulness, output-field, quote, source-label, and valid-JSON rules; the user prompt contains only `QUERY`, `BATCH`, and `SOURCE`.
- Changed the expected `search_findings` JSON field order so `source_label` is the first field in every finding object, reducing local-model omissions seen in LM Studio logs.
- Reworked `detect_contradiction_candidates` prompting into the same Hungarian system prompt plus dynamic-only user prompt pattern, with dynamic data limited to `QUERY`, `MAX_CANDIDATES`, and selected `CLAIM_PAIRS`.
- Added latest-run diagnostics to the `Kutatási találatok` panel, showing saved finding count and backend-validation rejected candidate count plus rejection reasons after `search_findings` runs.
- Improved `search_findings` backend validation diagnostics so rejected LLM findings report whether the `source_label` is unknown or the `quote_text` cannot be found in the claimed source chunk.
- Changed `search_findings` quote validation to three stages. Exact quote matches remain `source_valid`; non-exact quotes are repaired to the best exact source substring and saved as `source_valid` / `unconfirmed` when enough source text can be recovered; valid-label findings whose quote cannot be repaired are still persisted as `source_invalid` / `unconfirmed` worklist items with unresolved quote spans, warning styling, and the `Nincs érvényes forráshivatkozás` label.
- Added source-context display support for unrepaired `source_invalid` research findings: research-finding API responses now include the referenced chunk/page text as context even when the invalid LLM quote cannot be located exactly.
- Extended the same source-context display behavior to converted structured objects in the review report: `source_invalid` report items now expose the referenced chunk/page text for inspection even when the quote itself has no exact source span.
- Fixed detached-source reattach so reattaching an invalid quote source no longer promotes the target object into the source-valid category. Claim/event/missing-item targets now recompute source validation from linked source references, and entity report status validates mention source references instead of relying only on link presence.
- Added source-context display to parked detached-source items: the detached-source API returns the referenced chunk/page text and the frontend displays it in a `Szövegrész megtekintése` details block.
- Removed the experimental `search_findings` prompt priority rule and the ambiguous "SOURCE directly supports the finding" task sentence because they could make the model treat the full QUERY phrase as something to prove rather than treating SOURCE as required support for returned findings.
- Added active/félretett worklist views for the `Teljes iratfeldolgozás` surface, with restore from félretett, deletion marking on cards, "összes látható törlésre jelölése", bulk soft-delete from the worklist toolbar, and display-label search within the prepared worklist.
- Added `POST /api/v1/cases/{case_id}/full-document-processing/items/bulk-delete` for grouped deletion of preparatory full-document worklist items.
- Moved LLM model status into a thin global top bar with grouped chat/embedding load and unload controls, and replaced the old per-workbench operation panel with a compact AI operation strip below the surface selector.
- Added `Design_documents/20_general_rag_question_answering_plan.md` and refreshed handoff/next-step documents so the next larger strategic slice is broad design for a general local RAG question-answering surface over selected imported/corpus material, while the strict worklist/source-validation workflows remain alongside it.
- Expanded the general RAG plan with a concrete first-step design for `iratgyujtemeny` / source-scope selection: many-to-many document collections, deduplicated active-document scope resolution, backend/API/audit/frontend/index-readiness planning, and explicit non-goals.
- Added `iratgyujtemeny` contract v1 to the general RAG plan: DB constraints, Pydantic schema shapes, service behavior, API endpoints/status codes, audit metadata, frontend minimal UX, backend/frontend test contracts, and a backend-first implementation order.

## 2026-05-26

### Changed

- Added `Design_documents/14_work_surface_ui_architecture_plan.md`, defining the AppShell, shared case context, surface navigation, and first work-surface rollout plan.
- Updated the next-step handoff so the immediate frontend target is the first AppShell/surface-navigation slice rather than adding more panels to the current workbench.
- Implemented the first work-surface navigation slice: the existing page is now `Ügy munkapad`, with placeholder surfaces for `Teljes iratfeldolgozás` and `Audit napló`.
- Expanded `Teljes iratfeldolgozás` from placeholder into a frontend-only first UI slice with active-document selection, profile selection, selected-document summary, and output scaffold.
- Added `Design_documents/15_full_document_processing_plan.md`, defining the backend contract for full-document processing runs and preparatory `document_processing_item` records.
- Added `Design_documents/16_large_case_document_storage_and_retrieval_plan.md`, making large-case storage/retrieval redesign the gate before full-document backend implementation.
- Added `Design_documents/17_storage_migration_impact_review.md`, mapping the current code dependencies on DB-stored page/chunk text and identifying `TextStore` / `SourceTextResolver` as the safest first refactor slice.
- Added `Design_documents/18_keyword_search_text_store_migration_plan.md`, defining the planned replacement for direct PostgreSQL FTS over full DB text fields with a metadata + `tsvector` search-entry layer backed by text-store quotes.
- Added `Design_documents/19_document_taxonomy_retirement_plan.md`, defining the staged retirement of import-time document taxonomy from frontend workflow, API/filter layers, and eventually database/search-entry columns.
- Added migration `0036_search_entries`, `DocumentSearchEntryModel`, and `app/services/lexical_index.py` writer helpers as the first keyword-search migration foundation.
- Added the first DB-backed `TextStore` / `SourceTextResolver` implementation and routed source-reference validation, finding extraction source text, embedding input, analysis previews, and source excerpts through it without changing runtime behavior.
- Added migration `0035_text_layer_manifests` with `document_text_layers` and `document_chunk_manifests` as the metadata contract for later file-backed extracted text and chunk manifests.
- Added JSONL page/chunk text-store helpers with per-record text hashes and file-level SHA256 manifest hashes.
- Wired TXT import to write physical `pages.jsonl` / `chunks.jsonl` files plus `document_text_layers` / `document_chunk_manifests` rows while preserving current DB-backed API behavior.
- Added a native PDF parser quality gate before page persistence: partial/low-quality parser results now keep the original PDF for OCR but do not create pages, text layers, chunks, or indexing material.
- Added an OCR quality decision gate before page persistence: clean OCR creates a reviewable text layer, partial OCR reports usable/failed pages without automatically creating a text layer, and fully unusable OCR points to discard/replace.
- Added a partial OCR acceptance backend slice: partial OCR writes staged OCR candidate pages, and selected usable pages can be explicitly promoted into a current OCR text-review layer.
- Wired clean native PDF parse, clean OCR, accepted partial OCR, and explicit chunk creation to write text-store manifests (`document_text_layers` / `document_chunk_manifests`) and JSONL files while keeping current DB-backed API behavior.
- Wired `lexical_index` search-entry population into text-layer and chunk-manifest persistence, so TXT import, clean native PDF text layers, clean/accepted OCR text layers, and explicit chunk creation now maintain `document_search_entries`.
- Switched active keyword search to query `document_search_entries.search_vector`; quote generation now reads source text through physical text-store helpers with DB fallback while preserving the existing `KeywordSearchHit` contract for keyword and hybrid search.
- Switched the first runtime source-text reads to prefer physical text-store with DB fallback for analysis run previews, review report source excerpts, and research-finding source excerpts.
- Extended text-store-first runtime reads to LLM SOURCE block construction, `search_findings` quote validation, source-reference quote/span validation, source-cited smoke analysis, and embedding input.
- Updated the verification baseline to `246 passed` and Alembic head `0036_search_entries`.
- Reframed the next backend direction around 5000+ document cases: PostgreSQL should keep metadata/workflow/audit/source references, extracted page/chunk text should move toward a data-root text store, and Qdrant should remain the retrieval index.
- Reframed document taxonomy as a transitional legacy workflow for large-case use: current code still contains group/type controls and filters, but the next cleanup target is removing that UX first, then retiring backend/API/filter/database remnants in controlled stages.
- Removed the frontend document taxonomy workflow from active UX: import no longer asks for document group/type, document details no longer expose reclassification, analysis source filtering no longer shows group/type filters, and the frontend no longer calls the document-taxonomy API.
- Added multi-file selection to the frontend TXT/PDF import control; selected files are uploaded sequentially through the existing single-document backend import endpoint.
- Removed selected-document page-range controls from the frontend analysis panel; selected-document `search_findings` now searches the whole selected document from the UI.
- Switched the default embedding profile to LM Studio model id `text-embedding-bge-m3` with `context_length=4096`, keeping embedding load payloads limited to fields LM Studio accepts for embedding models.
- Marked the previous Qwen embedding profile as retired from the active default path; BGE-M3 is now the intended embedding baseline.
- Changed the default analysis `Batch meret` to `1` while keeping backend/frontend validation limits unchanged.
- Generalized the `search_findings` prompt's positive focus rule from person-only matching to concrete focus items such as persons, organizations, locations, phone numbers, email addresses, license plates, money amounts, case references, document references, and attachments.
- Kept `search_findings` operational instructions in English while requiring Hungarian source processing, Hungarian user-facing output fields, and character-exact Hungarian `quote_text` copying.
- Tuned the `search_findings` prompt to keep the QUERY focus as the gate while accepting clear Hungarian inflected forms of the same focus item.
- Earlier `Batch meret` default tuning to `5` has been superseded by the current default `1`; backend/frontend validation remains `1..15`.
- Added a static frontend focus helper explaining that short concrete focus terms may work better with `Batch meret` between `1` and `3`.
- Reordered the next larger project direction: first use the dedicated work-surface UI architecture, then build a full-document processing surface for already uploaded documents, and move the full `Audit naplo` API/panel after that.
- Fixed hybrid source selection so it collects candidates across all query variants before applying the final chunk cap; later keyword/normalized query hits are no longer starved by the first semantic result set.
- Retired the backend document taxonomy API/filter slice from active workflow: removed the routed `document-taxonomy` endpoint, removed document reclassification routing/service/schema, removed import-time group/type form fields, and removed taxonomy filters from search/index/analysis request paths.
- Removed the remaining document taxonomy DB/model/search-entry layer through migration `0037_remove_doc_taxonomy`: `documents.document_group_code`, `documents.document_type_code`, denormalized `document_search_entries` taxonomy columns, related indexes/constraints, the taxonomy core registry, response labels, and test fixtures are no longer active.
- Tightened the storage migration path: explicit chunk creation now reads reviewed page text through the text-store helper, and active service fallbacks route through `read_page_text` / `read_chunk_text` instead of scattered direct DB text field access.
- Switched page/chunk detail API response construction to text-store-first text population while preserving the existing `extracted_text` / `chunk_text` response fields for frontend compatibility.
- Added migration `0038_nullable_text_fields`, making `document_pages.extracted_text` and `document_chunks.chunk_text` nullable compatibility fallback fields while service/API reads stay text-store-first.
- Added the first full-document processing backend foundation through migration `0039_doc_proc_items`: `document_processing_items`, `full_document_processing` run type, `document_processing_item` analysis output type, SQLAlchemy model, schemas, profile registry, and read/list/status API skeleton.
- Removed legacy PostgreSQL full-text storage for page/chunk bodies through migration `0040_drop_db_text_cols`: `document_pages.extracted_text`, `document_chunks.chunk_text`, and the old direct FTS indexes are gone. API response fields with those names remain compatibility fields populated from the data-root text store.
- Added migration `0041_detach_audit_lifecycle`, which keeps `audit_events.case_id` and `audit_events.analysis_run_id` as historical UUID metadata without hard foreign keys to case/run rows.
- Added permanent full-case deletion through `DELETE /api/v1/cases/{case_id}` and a frontend `Ügy végleges törlése` action with typed-name confirmation. The deletion removes case-owned DB rows, case storage files, and Qdrant points for the case while preserving audit rows and writing a global `case_deleted` audit event.
- Added the first full-document processing run-start API/service slice: selected document + profile creates a `full_document_processing` analysis run, reads the selected page range from the data-root text store, sends that range to the local chat model in one request, validates source quotes before persistence, and stores valid preparatory `document_processing_items`.
- Analysis run output summaries now include `document_processing_item` outputs.
- Wired the `Teljes iratfeldolgozás` frontend surface to backend profiles, run-start execution, active item listing, source-evidence display, set-aside/delete status changes, and focus handoff into the `Ügy munkapad`.
- Updated the verification baseline to `246 passed` and Alembic head `0041_detach_audit_lifecycle`.

## 2026-05-25

### Changed

- Increased the configured LM Studio chat-model context window to `context_length=30720` while keeping embedding model loading at `context_length=12288`.
- Switched the active `search_findings` operational prompt instructions to English while explicitly requiring Hungarian source processing, Hungarian user-facing output fields, and character-exact Hungarian `quote_text` copying.
- Added person-identity-focused prompt wording and retrieval stopword tuning for generic Hungarian query phrases such as `Minden információ a következő személyről ...`.

## 2026-05-24

### Added

- Added searchable overlay target selectors for merge, direct source move, manual contradiction selection, and detached-source reattach workflows.
- Added permanent detached-source deletion and removed the old irrelevant/discarded parked-source state through Alembic migration `0032_delete_discarded_detached_sources`.
- Added permanent cleanup for corrected or source-invalid review-report items through Alembic migration `0033_review_delete_action`.
- Added audited title/description editing for source-valid, non-corrected review-report items through Alembic migration `0034_review_edit_text`.
- Added direct attachment of selected readonly chunk text to existing structured objects through the manual source workflow, with backend validation for active source material, target ownership/type, and exact duplicate attachments.

### Changed

- Removed user-entered comments from manual source attachment to existing objects; the operation is tracked by system provenance and audit/review records instead.
- Updated the verification baseline to `225 passed` and Alembic head `0034_review_edit_text`.
- Kept the next larger direction as the dedicated full `Audit naplo` API/panel backed by `audit_events`.

## 2026-05-23

### Added

- Added claim-level merge, source detach, direct source move, and detached-source reattach support so claims have the same source-management flexibility as entities, events, and missing item candidates.
- Added Alembic migration `0031_detached_source_claims` so `detached_source_items` can track claim-origin detached sources.
- Added frontend claim merge controls and claim source movement targets in the review report/object detail workflow.

### Changed

- Relaxed subtype restrictions for merge, direct source move, and detached-source reattach. These operations remain constrained to the same main object type, but no longer require matching claim/event/entity/missing-item subtype values.
- Updated the active analysis/search baseline around `search_findings`: `Szovegresz plafon` defaults to 30 and is capped at 50.
- Updated the verification baseline to `220 passed` and Alembic head `0031_detached_source_claims`.

## 2026-05-22

### Changed

- Retired the legacy raw chunk-based automatic extraction modules from active code paths: `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, and `detect_missing_items` are no longer accepted by backend dispatch and no longer appear in the frontend module selector.
- Removed the retired modules' service files, response schema entries, frontend response-count fields, and prompt/validation tests. Old module keys now return `Unsupported analysis module`.
- Removed `summary_item` from the active system because no current workflow can produce semantically valid summary items: API/router/service/schema/model files, review-report inclusion, frontend filters/review path mapping, output-summary handling, tests, tables, and accepting DB constraints were removed through migration `0025_remove_summary_items`.
- Kept `search_findings` as the active source-bound research workflow and `detect_contradiction_candidates` as the downstream claim-pair workflow.
- Added `search_findings` to document discard analysis-history protection so a finding search run can block unsafe early document discard even when evaluated through run history.
- Updated the verification baseline to `212 passed` and Alembic head `0025_remove_summary_items`.

## 2026-05-20

### Added

- Added `Design_documents/12_source_bound_findings_model_plan.md`, defining the planned source-bound `research_finding` model: query-driven source findings first, non-binding type suggestion second, and human-controlled conversion into structured objects.
- Added `Design_documents/13_legacy_analysis_module_retirement_plan.md`, defining a clean retirement path for the raw chunk-based automatic extraction modules without silent aliases or leftover legacy code paths.
- Added graph-view compatibility as an explicit planning constraint for the future `research_finding` schema, preserving source-reference -> finding -> structured-object relationships without introducing a graph database yet.
- Added the first `research_finding` backend foundation: SQLAlchemy model, schemas, internal create/list/get service, read-only list/detail API, analysis-run output summary support, and Alembic migration `0021_research_findings`.
- Added the first LLM-backed source-bound finding search backend module, `search_findings`, which creates source references, persists `research_finding` records with non-binding `suggested_type`, records analysis run provenance, and is enabled by Alembic migration `0022_search_findings_run_type`.
- Added the first frontend workflow for source-bound research findings: `Kutatási találatok keresése` is selectable in the analysis panel, persisted findings refresh after runs, and the `Kutatási találatok` panel shows type suggestion, relevance reason, source/worklist status, and source-reference quotes.
- Added human-controlled research-finding conversion: `research_finding` records can be converted into structured claim/entity/event/missing item candidate objects by reusing the same source reference through the manual-entry path, preserving provenance and marking the finding with target object metadata.
- Added research-finding worklist controls: findings can be set aside, restored to the active list, marked for deletion, and bulk-deleted. Converted findings disappear from the active worklist while the created structured object keeps the source-bound workflow.
- Added document lifecycle/parking support with `active`, `excluded`, and `archived` states, status-change metadata, audit events, frontend controls, and Alembic migration `0020_document_lifecycle_status`.
- Added safe early document discard/delete for documents that have not yet become analysis/source material; documents with chunks, source references, analysis inputs, or review consequences are parked through exclude/archive instead of physical deletion.
- Added active-document enforcement across new source-producing workflows: indexing, retrieval, raw-chunk analysis, source-reference creation, manual source-bound object creation, detached-source reattachment, source move/detach/merge, and contradiction candidate creation/claim selection.
- Added review report lifecycle visibility for source documents so historical findings from excluded/archived documents remain visible while clearly marked as inactive-source material.
- Added frontend refresh behavior after document lifecycle changes so report items, selected item details, merge targets, source movement targets, detached-source controls, and manual contradiction claim options reflect the current active/inactive source state.

### Changed

- Recorded the strategic analysis-model direction change: raw chunk-based automatic `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, and `detect_missing_items` should be treated as retirement candidates rather than the future main workflow.
- Converted `research_finding` from a review object into a worklist layer through migration `0024_research_findings_worklist`: removed `research_findings.review_status`, removed `research_finding` from `human_reviews`, and kept review/export behavior on converted structured objects instead.
- Updated the verification baseline to `230 passed` and Alembic head `0024_research_findings_worklist`.
- Recorded the next larger direction as clean removal of the then still-present raw chunk-based automatic extraction modules according to `Design_documents/13_legacy_analysis_module_retirement_plan.md`; the full `Audit naplo` API/panel remains the following major direction after that cleanup.

## 2026-05-14

### Added

- Added `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`, which defines the planned document group/type taxonomy, `uncategorized` migration strategy, import validation direction, and later analysis source-filtering path for large multi-document cases.
- Added explicit cross-reference notes to the older design documents where the current implementation intentionally differs from the original plan, pointing to the newer pipeline, batch-processing, runtime, and taxonomy documents instead of rewriting the historical design text.
- Added the first structured document taxonomy backend slice: central taxonomy registry, `GET /api/v1/document-taxonomy`, `document_group_code` / `document_type_code` document fields, import-time taxonomy validation, default `uncategorized / uncategorized`, and Alembic migration `0018_document_taxonomy`.
- Added frontend taxonomy support for document import and document lists: dependent Hungarian document group/type dropdowns are loaded from `GET /api/v1/document-taxonomy`, imports submit structured taxonomy codes, and document cards/details show the structured labels.
- Added backend analysis source filtering by structured document taxonomy and explicit document list: `document_group_code`, `document_type_code`, and `document_ids` are now accepted for case-scope raw-chunk modules and applied consistently to keyword, semantic, and hybrid retrieval.
- Added frontend analysis source-filter controls for whole-case raw-chunk modules: optional document group filter, dependent document type filter, and concrete document checkbox selection. The filters are sent as `document_group_code`, `document_type_code`, and `document_ids`.
- Extended semantic index status and background chunk indexing to the same structured source subset: `document_ids`, `document_group_code`, and `document_type_code` now affect index readiness checks and index jobs, and semantic/hybrid execution checks the resolved document subset instead of the whole case.
- Removed the legacy free-text `documents.document_type` path from backend models, import/search schemas, frontend document types/list display, and the database through Alembic migration `0019_drop_legacy_document_type`; structured taxonomy codes are now the only document classification path.
- Added audit-tracked document reclassification through `PATCH /api/v1/cases/{case_id}/documents/{document_id}/taxonomy` plus a frontend `Besorolas modositasa` block in the document detail panel.
- Updated the verification baseline to `200 passed` and Alembic head `0019_drop_legacy_document_type`.
- Added local chunk indexing foundation: `POST /api/v1/cases/{case_id}/indexes/chunks` embeds current chunks with the configured local embedding model, upserts vectors into Qdrant, stores chunk embedding metadata, and records `embed_chunks` analysis run provenance.
- Added hybrid chunk search foundation: `POST /api/v1/cases/{case_id}/search/hybrid` supports `keyword`, `semantic`, and `hybrid` strategies over source chunks.
- Added `retrieval_strategy` to batch-capable focused-query analysis requests, with analysis run chunk inputs recording `retrieval_match_type`.
- Added frontend controls to index chunks and choose keyword/semantic/hybrid source retrieval for focused-query raw-chunk analysis.
- Added explicit LM Studio embedding model load workflow and auto-load before embedding calls.
- Added model-specific Qdrant chunk collections and model-aware reindex eligibility so vectors created with a previous embedding model do not block indexing with the current model.
- Added `retrieval_strategy` to persisted raw-chunk analysis input parameters so hybrid/semantic focused runs remain auditable at the run level as well as the chunk-input level.
- Added a strict JSON-repair retry for claim extraction when the model returns JSON-invalid quote text, preserving the same source/quote validation after repair.
- Added deterministic lenient claim JSON field recovery for malformed `quote_text` values with internal quotes when the model and JSON-repair pass both return invalid JSON; recovered items still pass the normal source quote validation before persistence.
- Reduced the default local load profile for the current workstation: chat `eval_batch_size` is now `6144`, and the default embedding model is `text-embedding-qwen3-embedding-4b`.
- Switched the default embedding model to `text-embedding-qwen3-embedding-4b@q6_k` for a lighter local LM Studio profile; chat model id remains `qwen/qwen3.5-9b`, with LM Studio expected to load the desired quantized variant behind that id.
- Recorded the next retrieval hardening direction: hybrid ranking calibration, semantic/hybrid document/case source selection, and frontend visibility into selected source chunks.
- Added the first calibrated hybrid ranking slice: hybrid retrieval now combines keyword score, semantic score, exact phrase evidence, and keyword/semantic overlap instead of sorting by a raw max score.
- Extended retrieval-aware source selection into document and case analysis modes.
- Documented the WSL/Codex frontend startup caveat: Vite can exit with `Hangup` after a plain background start, so Codex-started frontend sessions should use `setsid` and verify the `5173` listener.
- Expanded frontend model status controls into a dedicated local model panel with separate chat and embedding load actions plus loaded-instance visibility.
- Added configurable embedding index batching through `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE`; chunk embeddings are now requested and upserted in smaller batches to reduce LM Studio timeout and RAM spikes.
- Added chunk index status API and frontend semantic index status panel; semantic/hybrid focused analysis is now blocked until the active source scope is indexed with the configured embedding model.
- Added background chunk indexing through `POST /api/v1/cases/{case_id}/indexes/chunks/jobs`; the frontend starts the job, polls index status, and shows latest-run progress instead of waiting for one long indexing request.
- Changed raw-chunk analysis source selection to require explicit focus text in focused-query, document, and case modes; missing/no-hit focus now fails clearly instead of falling back to first chunks.
- Replaced the frontend analysis `Limit` control with `Szovegresz plafon` for raw-chunk modules; it defaults to 20, is capped at 30 in both frontend and backend validation, and focused-query mode now uses the same chunk-plafon plus batch-size workflow as document/case modes.
- Kept chunk indexing separate from the analysis chunk plafon: frontend background index jobs request the selected source scope up to the indexing endpoint cap instead of indexing only the analysis-sized subset.
- Added human-readable analysis run detail summaries: selected chunk inputs now expose document/page/chunk metadata, retrieval match type/score, batch position, and preview text, while output rows expose short object summaries.
- Updated the page-local text chunker to `char_window_v2`: it now prefers paragraph breaks, then sentence-end breaks, then line breaks/spaces before hard character limits, without allowing chunks to span processed page boundaries.
- Added backend OCR recommendation metadata to document responses and changed the frontend OCR action to follow that recommendation, distinguishing recommended OCR from optional OCR checks on suspicious native-text PDFs.
- Fixed document detail page/chunk listing after OCR so the default API/UI view returns only current page and chunk versions; previous native versions remain audit/version history but no longer appear as duplicate current content.
- Added Alembic migration `0017_text_review_status` and the `text_review_required` document status for explicit PDF text-layer review.
- Changed native PDF import and OCR to create current pages without immediately creating chunks; users now explicitly create chunks afterward through `POST /api/v1/cases/{case_id}/documents/{document_id}/chunks`, which records a `chunk_document` analysis run.
- Added frontend `Szovegreszek letrehozasa` action for `text_review_required` documents and localized the new status as `Szoveg ellenorzesre var`.
- Removed the obsolete `focused_query` analysis source mode from frontend and backend; raw-chunk modules now choose only between whole-case (`case`) and selected-document (`document`) source scopes, with focus text handled as a separate required field.
- Removed the legacy analysis-module request `limit` field. Raw-chunk modules use `max_chunks` for source selection, and contradiction detection uses the explicit `contradiction_candidate_limit` field.
- Made contradiction candidate detection focus-required in both frontend and backend, exposed its separate candidate cap as `contradiction_candidate_limit`, and kept claim-focus matching accent-preserving with two-character minimum terms.
- Kept analysis source-selection query variants accent-preserving and lowered their minimum term length to two characters, aligning raw-chunk retrieval fallback terms with Hungarian text.
- Added analysis page-range filtering (`page_start`, `page_end`) inside the existing case/document source scopes. Keyword, semantic, and hybrid raw-chunk retrieval now constrain selected chunks by overlapping page range.
- Refined raw-chunk analysis page ranges to selected-document scope only. Whole-case analysis no longer shows or requires page fields; selected-document analysis defaults `Oldaltol/Oldalig` to the document bounds, while the backend falls back to the full document when page fields are omitted and rejects out-of-document ranges.
- Capped the effective `extract_events` batch size at 2 chunks to avoid local LM Studio chat timeouts on larger semantic result sets while preserving the requested batch size in analysis run input metadata.
- Added `Design_documents/10_analysis_batch_processing_plan.md` for the next analysis architecture step: shared source selection, chunk batching, batch metadata, exact deduplication, and batch-capable `extract_claims` as the first target.
- Added analysis module request fields for `source_mode`, `document_id`, `max_chunks`, and `batch_size`.
- Added shared source chunk selection for focus-based retrieval, document, and case source modes. The obsolete `focused_query` source mode was later removed.
- Added deterministic chunk batching and batch metadata for analysis run inputs.
- Added batch-capable `extract_claims` execution with exact in-run deduplication and parent analysis run summary counts.
- Added batch-capable `extract_events` execution with exact in-run deduplication and parent analysis run summary counts.
- Added batch-capable `extract_entities` execution with exact in-run deduplication and parent analysis run summary counts.
- Added batch-capable `summarize_case` execution with conservative per-batch summary item limits, exact in-run deduplication, and parent analysis run summary counts.
- Added batch-capable `detect_missing_items` execution with exact in-run deduplication and parent analysis run summary counts.
- Added regression coverage for document-mode source selection, focused-query validation, deterministic batching, and batch prompt metadata.
- Added regression coverage for `detect_contradiction_candidates` when fewer than two source-valid claims are available.
- Added deterministic backend claim-pair selection for `detect_contradiction_candidates`, including pair limits, focus filtering over claim/source text, selected-pair audit metadata, and validation that rejects unselected claim pairs.
- Added contradiction candidate quality safeguards: same pair/type deduplication, conservative severity normalization, and deterministic pair-bound titles/descriptions generated from selected source-cited claims.
- Added `claim_review_scope` for `detect_contradiction_candidates`; the default `reviewable` scope excludes rejected claims while allowing `new`, `needs_review`, `verified`, and `corrected` source-valid claims.
- Added explicit contradiction qualification for `detect_contradiction_candidates`; persisted candidates now require `is_contradiction_candidate=true` and a concrete `conflict_basis`, while related/non-conflicting pairs are rejected or reported as unsupported.
- Added historical deduplication before persistence for repeated analysis runs across claims, events, summary items, missing item candidates, and contradiction candidates.
- Added regression coverage for analysis deduplication normalization and content-matched duplicate detection.
- Added entity merge-on-extraction behavior: repeated content-matched entities reuse the existing entity and add/link mentions instead of creating duplicate entity review objects.
- Added explicit entity merge workflow with an API endpoint and frontend `Osszevonas` action so ambiguous identity decisions remain human-reviewed instead of automatic alias guesses.
- Moved frontend entity merge target selection to the full case entity list and exposed quick merge controls directly on report item cards as well as the object detail panel.
- Added explicit event merge workflow with API and frontend controls; event source links move to the selected target event, duplicate source links are skipped, and the source event is marked `corrected`.
- Added explicit missing item candidate merge workflow with API and frontend controls; source links move to the selected target candidate, duplicate source links are skipped, and the source candidate is marked `corrected`.
- Added audit-tracked source detach workflows for entities, events, and missing item candidates, with frontend `Levalasztas` actions on source details when a concrete source-link id is available.
- Added `detached_source_items` persistence and a frontend `Levalasztott forrasok` panel so detached source links keep their source reference and detached-from object snapshot.
- Added parked-source reattach/discard actions and direct same-type source move controls for entity, event, and missing item candidate sources.
- Added persisted reattach target fields for detached source items so the parked-source list shows which object received a reattached source.
- Added source-bound manual object creation from selected document chunk text for claims, entities, events, and missing item candidates, tracked through `manual_entry` analysis runs.
- Added source-bound manual object creation from detached source items, marking the detached item handled by the newly created object.
- Added manual contradiction candidate creation from two source-valid, non-rejected claims, with readonly claim/source previews in the frontend and `manual_entry` analysis run provenance in the backend.
- Hardened LLM JSON handling for analysis modules by extracting a JSON object from otherwise valid responses with extra surrounding text, while still rejecting malformed JSON.
- Added frontend source scope controls for batch-capable raw-chunk analysis modules, including selected document, whole case, focus text, max source chunks, and batch size.
- Added frontend support for the contradiction claim-pair workflow: required focus, claim review scope, and candidate cap in the analysis panel, claim-selection metrics, selected pair display, claim pair membership display, claim-pair based analysis summary text, and conservative review notes for contradiction candidates.
- Changed frontend analysis focus input to start empty for every module; module-specific examples are placeholders only and are not submitted unless the user types text.
- Removed redundant review report quick-filter buttons; review report filtering now uses the dropdown controls only.

### Changed

- Updated handoff/session documentation to make the analysis batch foundation the next logical development direction while preserving focus-based source selection.
- Updated the verification baseline to `165 passed` and Alembic head `0016_manual_entry`.
- Recorded live batch analysis smoke results for `extract_claims` in document and case source modes; both completed with `validation_status=passed`.
- Recorded live batch analysis smoke results for `extract_events` in document and case source modes; both completed with `validation_status=passed`.
- Recorded live batch analysis smoke results for `extract_entities` in document and case source modes; both completed with `validation_status=passed`.
- Recorded live batch analysis smoke results for `summarize_case` in document and case source modes; both completed with `validation_status=passed`.
- Recorded live batch analysis smoke results for `detect_missing_items` in document and case source modes; both completed with `validation_status=passed`.
- Verified the frontend build after adding source scope controls.
- Verified the frontend build after adding contradiction claim-pair UI support.
- Verified the frontend build after adding manual contradiction candidate UI support.
- Hardened the `extract_events` prompt against invalid JSON from long quotes and unescaped double quotes; focused query `narrátor Dupin` now returns `validation_status=passed`.
- Made all-failed `extract_events` batch errors include the first batch failure reason instead of only a generic message.
- Clarified `detect_contradiction_candidates` as a claim-pair module rather than a raw chunk batch module.
- Made `detect_contradiction_candidates` return a clean `validation_status=warning` precondition result when fewer than two source-valid claims exist, with claim-selection metadata recorded as analysis run input and no LLM call.
- Recorded live pair-selection smoke for `detect_contradiction_candidates`: focused query selected 6 claims and 8 backend pairs from a claim-rich case, then returned 2 source-cited `time_conflict` candidates.
- Recorded live contradiction quality smoke: time-conflict candidates now persist as conservative `medium` severity with deterministic titles and pair-bound descriptions, instead of preserving overstated model wording.

## 2026-05-13

### Added

- Added Alembic migration `0013_processing_runs` to allow document-processing pipeline run types and document/page/chunk analysis run outputs.
- Added explicit document processing validation endpoint at `POST /api/v1/cases/{case_id}/documents/{document_id}/process`.
- Added native-text PDF import foundation using a configurable `docling_then_pypdf` parser profile through the existing document import endpoint.
- Added a PDF parser adapter layer so Docling can be the primary parser profile while `pypdf` remains a local fallback for native-text PDF extraction.
- Installed and smoke-tested Docling in the project `.venv`; explicit `BOBERDETECTIVE_PDF_PARSER=docling` PDF import now returns parser `docling` and a passed `parse_document` run.
- Updated the Docling adapter to disable OCR, table structure extraction, and remote services for the native-text parser profile.
- Hardened native PDF parsing with multi-page, corrupt-PDF, and partially-empty-page coverage.
- Partially empty native-text PDF imports now complete as `review_required` with `parse_document` validation `warning`.
- Image-only/scanned PDFs with no native text now remain importable as audit-tracked `review_required` documents, so the explicit OCR endpoint can process them.
- Added explicit Tesseract OCR foundation for PDF documents at `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr`.
- OCR runs render PDF pages to data-root derived storage, run Tesseract without shell invocation, persist OCR page/chunk versions, and record `ocr_document` analysis run provenance.
- Added PDF parsing tests with generated minimal native-text and scanned-style/image-only PDF fixtures.
- Added synthetic local PDF sample generation under `samples/pdf/` for native-text, good scanned, weak scanned, and mixed empty-page cases.
- Added parser/OCR sample evaluation script that reports native parse result, OCR text length, Tesseract confidence, and quality issues.
- Added average Tesseract confidence capture from TSV output on a 0..1 scale and `low_ocr_confidence` OCR quality warnings.
- Fixed OCR persistence for real documents by normalizing Tesseract's 0-100 confidence values to the database's 0..1 scale.
- Fixed document page API serialization for OCR pages by returning Decimal-backed OCR confidence as a numeric value instead of validating it as a string.
- Raised the default upload limit to 50 MiB through `BOBERDETECTIVE_MAX_UPLOAD_BYTES` and made upload-too-large errors include the configured size.

### Changed

- Updated the verification baseline to `120 passed` and Alembic head `0013_processing_runs`.

## 2026-05-11

### Added

- Added `Design_documents/06_document_processing_pipeline_v1.md` with the MVP import, parsing/OCR, page text, chunking, embedding, indexing, validation, and audit pipeline design.
- Added `Design_documents/07_prompt_and_json_schema_collection_v1.md` with MVP analysis module prompt contracts, JSON output schemas, and validation rules.
- Added `Design_documents/08_mvp_backlog_and_implementation_sequence.md` with phased implementation order, validation gates, and first sprint scope.
- Added `Design_documents/09_environment_verification_and_security_baseline.md` with WSL/tooling checks, LM Studio reachability result, missing dependencies, and secure development baseline.
- Added initial Python/FastAPI backend scaffold with health endpoint, config loader, JSONL audit writer skeleton, secure storage path resolver, and pytest smoke tests.
- Added `.venv`, `pyproject.toml`, `.env.example`, and `.gitignore`.
- Initialized Git repository on branch `main`.
- Added Docker Compose development runtime for PostgreSQL 16 and Qdrant 1.15.5.
- Added SQLAlchemy/psycopg DB layer and Alembic migration foundation.
- Added initial `users`, `cases`, `case_users`, and `audit_events` tables.
- Added case create/list API with DB and JSONL audit on case creation.
- Added audit serialization tests for stable event identity and secret redaction.
- Added `documents`, `document_pages`, and `document_chunks` SQLAlchemy models.
- Added Alembic migration `0002_documents_pages_chunks` with constraints, uniqueness rules, and PostgreSQL full-text indexes for page/chunk text.
- Added immutable TXT import API at `POST /api/v1/cases/{case_id}/documents`.
- Added document list and document page list API endpoints.
- Added TXT import validation for extension/content type, UTF-8 decoding, empty files, and upload size limit.
- Added TXT import tests for unsupported type, invalid encoding, size limit, and filename handling.
- Added deterministic TXT chunk creation during import using `char_window_v1`.
- Added document chunks list API endpoint.
- Added chunker tests for offset preservation, whitespace handling, and invalid chunk size.
- Added keyword search API at `POST /api/v1/cases/{case_id}/search/keyword`.
- Added PostgreSQL full-text search over current document pages and chunks.
- Added keyword search response schemas with source identifiers, document metadata, page ranges, scores, and plain-text quotes.
- Added keyword search tests for request validation and quote generation.
- Added `source_references` SQLAlchemy model and Alembic migration `0003_source_references`.
- Added source-reference create/list/get/validate API endpoints.
- Added source-reference quote validation against page/chunk source text.
- Added source-reference tests for payload offsets and quote span validation.
- Added `LLMProvider` abstraction with an OpenAI-compatible local provider for LM Studio.
- Added `GET /api/v1/system/llm/smoke` to check local LLM provider reachability and configured model availability.
- Added LLM provider tests using `httpx.MockTransport`.
- Added `analysis_runs`, `analysis_run_inputs`, and `analysis_run_outputs` SQLAlchemy models and Alembic migration `0004_analysis_runs`.
- Added analysis run list/detail API endpoints.
- Added analysis run lifecycle helpers with DB + JSONL audit events.
- Added analysis run lifecycle validation test.
- Added synthetic local LLM benchmark for source-faithfulness and JSON-format adherence.
- Added benchmark scoring tests and raw-output reporting option.
- Added LM Studio native API provider support for `/api/v1/chat`.
- Added explicit LM Studio native configured chat-model loading through `/api/v1/system/llm/load-chat-model`.
- Added an LM Studio native chat auto-load guard that reuses a loaded configured-model instance when present and loads it with the configured GPU-oriented profile when missing.
- Added native benchmark mode with `reasoning: "off"` for Qwen-style reasoning models.
- Documented LM Studio native API optimization notes: `max_output_tokens`, `store: false`, `system_prompt`, model-specific reasoning control, and later `/api/v1/models/load` tuning parameters.
- Added first source-cited analysis smoke endpoint at `POST /api/v1/cases/{case_id}/analysis/source-cited-smoke`.
- Added smoke analysis service that records analysis run inputs/outputs, calls Qwen through LM Studio native API, validates quotes, and creates source references.
- Added source-cited smoke parsing/validation tests.
- Added `claims` and `claim_sources` SQLAlchemy models and Alembic migration `0005_claims`.
- Added claim list/detail API endpoints.
- Added claim creation service that requires an analysis run and source reference.
- Wired source-cited smoke output into persisted claims and claim_sources.
- Added claim validation tests.
- Added `human_reviews` SQLAlchemy model and Alembic migration `0006_human_reviews`.
- Added claim review API endpoint with `verify`, `reject`, `mark_needs_review`, and `comment` actions.
- Added append-only review history to claim detail responses.
- Added claim review status mapping test.
- Added generalized analysis module API at `POST /api/v1/cases/{case_id}/analysis/modules/{module_key}`.
- Added first supported analysis module, `extract_claims`, with keyword chunk retrieval, LM Studio native execution, quote validation, source-reference creation, claim persistence, and analysis run provenance.
- Added analysis module tests for fenced JSON parsing, object-shape validation, labeled chunk quote validation, and claim type normalization.
- Added `events` and `event_sources` SQLAlchemy models and Alembic migration `0007_events`.
- Added event list/detail API endpoints.
- Added `extract_events` analysis module with keyword chunk retrieval, LM Studio native execution, quote validation, source-reference creation, event persistence, and analysis run provenance.
- Added analysis module tests for event quote validation and event type/time precision normalization.
- Added keyword search prefix tsquery tests.
- Added case review report API at `GET /api/v1/cases/{case_id}/review-report`.
- Added read-only review report schemas and service that combine claim/event items with source references, review status, source validation status, analysis run ids, and review history.
- Added review report count tests.
- Added `exports` and `export_items` SQLAlchemy models and Alembic migration `0008_exports`.
- Added JSON review report export API at `POST /api/v1/cases/{case_id}/exports`.
- Added export list/detail/download endpoints.
- Added export file writing under the case export directory with SHA256 recording.
- Added `export_created` audit events and export item tracking.
- Added export filtering tests.
- Added export review API at `POST /api/v1/cases/{case_id}/exports/{export_id}/reviews`.
- Added append-only export review history to export detail responses.
- Added `export_review_recorded` audit events.
- Added export review status mapping tests.
- Added `CURRENT_STATE.md` as the compact Session Handoff Baseline v1 for fresh Codex sessions.
- Added HTML review report export support through the existing export API.
- Added HTML escaping for review report export content.
- Added an HTML export XSS regression test.
- Added event review API at `POST /api/v1/cases/{case_id}/events/{event_id}/reviews`.
- Added append-only event review history to event detail responses.
- Added `event_review_recorded` audit events.
- Added event review status mapping and validation tests.
- Added shared review service helper for claim/event/export review workflows.
- Added shared review helper tests.
- Added `entities` and `entity_mentions` SQLAlchemy models and Alembic migration `0009_entities`.
- Added entity list/detail API endpoints.
- Added `extract_entities` analysis module with keyword chunk retrieval, LM Studio native execution, quote validation, source-reference creation, entity/mention persistence, and analysis run provenance.
- Added entity service and entity extraction validation tests.
- Added entity review API at `POST /api/v1/cases/{case_id}/entities/{entity_id}/reviews`.
- Added append-only entity review history to entity detail responses.
- Added `entity_review_recorded` audit events.
- Added entity review status mapping and validation tests.
- Added entity items to the case review report and review report exports.
- Added case review report filters for object type, review status, and source validation status.
- Added optional export `report_filters` for JSON/HTML review report exports.
- Added expanded review report source details: document filename/SHA256, quote offsets, chunk/page metadata, and bounded source excerpts.
- Added module-specific analysis service files for claim, event, and entity extraction plus common analysis module helpers.
- Added `summary_items` and `summary_item_sources` SQLAlchemy models and Alembic migration `0010_summary_items`.
- Added summary item list/create/detail API endpoints and append-only review workflow.
- Added summary item inclusion in case review reports through `object_type=summary_item`.
- Added `summarize_case` analysis module foundation with source-cited summary item persistence.
- Added analysis module retrieval fallback query generation for broader natural-language Hungarian prompts.
- Added `contradiction_candidates` and `contradiction_candidate_sources` SQLAlchemy models and Alembic migration `0011_contradiction_candidates`.
- Added contradiction candidate list/create/detail API endpoints and append-only review workflow.
- Added contradiction candidate inclusion in case review reports through `object_type=contradiction_candidate`.
- Added `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs.
- Added `missing_item_candidates` and `missing_item_candidate_sources` SQLAlchemy models and Alembic migration `0012_missing_item_candidates`.
- Added missing item candidate list/create/detail API endpoints and append-only review workflow.
- Added missing item candidate inclusion in case review reports through `object_type=missing_item_candidate`.
- Added `detect_missing_items` analysis module with chunk retrieval, LM Studio native execution, quote validation, source-reference creation, missing-item candidate persistence, and analysis run provenance.
- Added missing item candidate analysis response schema and validation tests.
- Added JSON/HTML export regression coverage for `missing_item_candidate` review report items.
- Added analysis retrieval fallback coverage for short Hungarian accusative forms such as `mellekletet` and `kamerafelvetelt`.
- Added minimal React/Vite frontend workbench scaffold with case create/list, TXT import, analysis run, review report, and JSON/HTML export controls.
- Added Vite API proxy from `/api` to local backend port `8000`.
- Added frontend review actions for report items using allowlisted object-type review endpoints.
- Added frontend source detail and review history display for review report items.
- Added frontend long-running operation feedback with elapsed time, current operation label, last action summary, and analysis output count.
- Added frontend document list and analysis run history views for the selected case.
- Added frontend document page/chunk drill-down and analysis run input/output detail views.
- Added frontend review report filters for object type, review status, and source validation status.
- Added frontend object detail panel for selected review report items.
- Added frontend focused review queue shortcuts and export history list.
- Added Hungarian UI labels for the frontend, including display mappings for backend enum/internal values.
- Added source-bound analysis retrieval fallback to first current case chunks when keyword retrieval has no hits.

### Changed

- Updated handoff/status files after the pipeline design so prompt and JSON schema collection became the next design step.
- Updated handoff/status files after the prompt/schema document so MVP backlog and implementation sequence is now the next design step.
- Updated handoff/status files after the backlog so environment verification and first implementation sprint are now the next steps.
- Updated handoff/status files after environment verification so the first implementation sprint is now the next step.
- Updated environment verification after tooling changes: Docker/PostgreSQL CLI/Tesseract/ShellCheck are now installed, and LM Studio is reachable on localhost.
- Added `bober` to the Docker group and verified Docker access from WSL.
- Started PostgreSQL and Qdrant via Docker Compose and verified both services are reachable on localhost.
- Recorded a WSL stability note after stuck `wsl.exe` processes were force-stopped and services were reverified.
- Applied Alembic migration `0001_initial_foundation` and smoke-tested case creation.
- Applied Alembic migration `0002_documents_pages_chunks` and verified the document persistence tables exist.
- Installed `python-multipart` for FastAPI multipart import support.
- Smoke-tested TXT import through FastAPI/TestClient against the PostgreSQL-backed app.
- Smoke-tested TXT import plus chunk retrieval through FastAPI/TestClient against the PostgreSQL-backed app.
- Smoke-tested keyword search through FastAPI/TestClient against the PostgreSQL-backed app.
- Applied Alembic migration `0003_source_references` and smoke-tested source-reference creation/validation.
- Smoke-tested LM Studio model-list reachability through the backend provider endpoint.
- Smoke-tested LM Studio model loading with `context_length=4096`, `eval_batch_size=4096`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`; LM Studio echoed the applied load config.
- Applied Alembic migration `0004_analysis_runs` and smoke-tested analysis run start/input/output/finish/detail retrieval.
- Ran initial OpenAI-compatible LM Studio model benchmark; Llama was the practical default under `/v1/chat/completions`.
- Re-ran the benchmark through LM Studio native API with Qwen reasoning disabled; final native run gave Qwen `12/12` and Llama `10/12`.
- Smoke-tested first source-cited analysis path end-to-end against PostgreSQL and LM Studio; validation passed and audit/provenance links were created.
- Applied Alembic migration `0005_claims` and smoke-tested claim persistence with one source reference.
- Applied Alembic migration `0006_human_reviews` and smoke-tested claim verification with audit/review history.
- Broadened the source-cited analysis path from a single smoke endpoint toward versioned MVP analysis modules.
- Changed keyword search from plain tsquery to sanitized prefix tsquery terms to make Hungarian suffix matching less brittle while keeping query construction controlled.
- Smoke-tested `extract_claims` through the generalized module endpoint; validation passed and 2 claims were persisted.
- Applied Alembic migration `0007_events` and smoke-tested `extract_events`; validation passed and 1 event was persisted.
- Smoke-tested the case review report after claim/event extraction; it returned 3 `needs_review` items with source references.
- Applied Alembic migration `0008_exports` and smoke-tested JSON review report export; it created 3 export items and a downloadable JSON file.
- Smoke-tested export review; a JSON export was marked `verified` through append-only human review history.
- Smoke-tested HTML review report export; it created 3 export items and downloaded as `text/html`.
- Smoke-tested event review; an extracted event was marked `verified` through append-only human review history.
- Refactored claim, event, and export review workflows to use the shared review helper for mapping, listing, record creation, and audit writing.
- Applied Alembic migration `0009_entities` and smoke-tested `extract_entities`; validation passed and 2 person entities were persisted with mentions.
- Smoke-tested entity review; an extracted entity was marked `verified` through append-only human review history.
- Smoke-tested entity report/export inclusion; extracted entities appeared in the review report and HTML export item tracking.
- Smoke-tested filtered review report/export flow for entity items with `needs_review` and `source_valid` filters.
- Expanded JSON/HTML report exports now carry the same source detail fields, with HTML escaping retained.
- Refactored `app/services/analysis_modules.py` into a thin public façade while preserving existing API behavior and compatibility imports.
- Applied Alembic migration `0010_summary_items`; latest verification baseline is `77 passed`.
- Smoke-tested `summarize_case` against LM Studio; targeted `telefonhivas` retrieval produced 3 source-cited summary items and review report inclusion.
- Re-smoke-tested `summarize_case` with the original broad/accented query after retrieval fallback; it produced 3 source-cited summary items.
- Applied Alembic migration `0011_contradiction_candidates`; latest verification baseline is `84 passed`.
- Latest verification baseline is `86 passed` after contradiction detection module validation tests.
- Smoke-tested `detect_contradiction_candidates` against LM Studio; a two-claim phone-call time conflict sample produced 1 source-cited `time_conflict` candidate and review report inclusion.
- Applied Alembic migration `0012_missing_item_candidates`; latest verification baseline is `92 passed`.
- Smoke-tested `detect_missing_items` against LM Studio; a referenced attachment/photo documentation sample produced 2 source-cited `attachment` candidates and review report inclusion.
- Latest verification baseline is `94 passed` after missing item analysis module validation tests.
- Smoke-tested missing item candidate JSON/HTML review report exports; both created 1 tracked export item and downloads included `missing_item_candidate`.
- Latest verification baseline is `95 passed` after missing item export coverage.
- Improved analysis retrieval fallback for short/inflected Hungarian queries; the formerly failing `Keress hivatkozott mellekletet.` smoke now produces a source-cited missing item candidate.
- Latest verification baseline is `100 passed` after LM Studio auto-load guard coverage.
- Verified frontend production build with `npm run build`.
- Verified frontend review action build and targeted backend review tests.
- Verified frontend source-detail build and targeted review report/export tests.
- Verified frontend operation-feedback build and full backend regression tests.
- Verified frontend document/history build and targeted document/analysis-run backend tests.
- Verified frontend drill-down build and full backend regression tests.
- Verified frontend review-filter/object-detail build and targeted review report/export backend tests.
- Verified frontend queue/export-history build and targeted export/review backend tests.
- Smoke-tested the frontend/API path end to end against the live backend and Vite dev server: case creation, TXT import, all MVP analysis modules, review queue filter, claim review, JSON export/list/download, frontend index, and Vite API proxy.
- Updated handoff guidance so fresh sessions read `CURRENT_STATE.md` alongside the existing project notes.
- Updated the strategic handoff direction: pause deep frontend polishing and return next to the backend document-processing foundation, starting with explicit processing runs and native-text PDF parsing.

## 2026-05-10

### Updated

- Folded the database schema pre-implementation review refinements into `Design_documents/03_database_schema_v1.md`.
- Added page/chunk versioning fields to the schema design.
- Promoted `summary_items` and `summary_item_sources` to MVP schema objects.
- Added `source_validation_status` to source-cited AI-output schema objects.
- Updated `README.md`, `AI_NOTES.md`, and `AGENTS.md` to reflect the completed schema and API design state.
- Updated `Design_documents/00_project_context_for_codex.md` so the current requested design step is document processing pipeline design.
- Added `Design_documents/05_api_design_v1.md` with the MVP API endpoint and workflow design.
- Updated handoff/status files so document processing pipeline design is the next design step.

### Added

- Added `Design_documents/03_database_schema_v1.md` with the PostgreSQL-oriented MVP database schema.
- Added `Design_documents/03a_database_schema_pre_implementation_review.md` with a short schema review before SQL implementation.
- Added `Design_documents/04_runtime_and_deployment_v1.md` describing the Windows 11 + WSL2 + LM Studio runtime direction.
- Added `AGENTS.md` as the Codex/agent handoff guide.
- Added `AI_NOTES.md` as the current project state and next-step handoff file.

### Changed

- Updated `Design_documents/00_project_context_for_codex.md` so LM Studio is the default development LLM provider.
- Updated `Design_documents/02_technical_architecture_v1.md` so the LLMProvider strategy uses LM Studio by default in development while preserving Ollama and llama.cpp / llama-server as replaceable local providers.

### Notes

- As of this 2026-05-10 design handoff, no source code implementation existed yet.
- The project is expected to move into a dedicated WSL2 Ubuntu workspace.
- LM Studio is expected to run natively on the Windows 11 host and be accessed from the WSL/Linux backend through a local OpenAI-compatible API.
