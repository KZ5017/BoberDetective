# Local Investigative Document Intelligence System

This repository contains the design and future implementation of a fully local, auditable investigative document intelligence system.

The system is intended to help process large collections of investigative and legal documents by producing source-cited, human-reviewable structured outputs.

It is not an autonomous decision-making system.

## Current status

Implementation started.

Completed:

- Concept and MVP requirements
- Technical architecture v1
- Database schema v1, including pre-implementation refinements
- Runtime and deployment v1
- API design v1
- Document processing pipeline v1
- Prompt and JSON schema collection v1
- MVP backlog and implementation sequence
- Environment verification and security baseline
- Analysis batch processing plan
- Initial Python/FastAPI scaffold
- Docker Compose PostgreSQL/Qdrant dev runtime
- Database migration foundation
- Case and audit persistence foundation
- Document/page/chunk persistence foundation
- Immutable TXT import API
- Explicit document processing validation run API
- Native-text PDF import foundation with configurable `docling_then_pypdf` parser profile
- Page-local `char_window_v2` chunking that preserves processed page boundaries and prefers paragraph/sentence breaks before hard limits
- Explicit Docling parser smoke passed; Docling is installed in the local `.venv`
- Explicit Tesseract OCR foundation for PDF documents
- Backend OCR recommendation metadata so the frontend can distinguish recommended OCR from optional OCR checks
- Explicit PDF text-review workflow: native PDF import and OCR create current pages first, then users create analysis-ready chunks with `Szovegreszek letrehozasa`
- Image-only/scanned PDFs without native text remain importable as `review_required` documents for explicit OCR processing
- OCR captures average Tesseract confidence on a 0..1 scale and flags low-confidence pages
- Document page API returns OCR confidence as a numeric value
- Generated local PDF samples and parser/OCR evaluation scripts under `samples/` and `scripts/`
- Default upload limit is 50 MiB and can be changed with `BOBERDETECTIVE_MAX_UPLOAD_BYTES`
- Batch-capable raw-chunk analysis modules with whole-case and selected-document source scopes plus required focus text
- TXT chunk creation
- Keyword search
- Source-reference foundation
- LLMProvider abstraction
- LM Studio model-list smoke endpoint
- LM Studio configured chat-model load endpoint with GPU-oriented load profile
- LM Studio native chat auto-load guard for the configured model
- Current chat load profile uses `qwen/qwen3.6-35b-a3b` with `context_length=61440`, `eval_batch_size=512`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`. The previous speed-optimized workstation profile remains `qwen/qwen3.5-9b` with the same context/attention/KV settings and `eval_batch_size=4096`.
- Analysis run provenance foundation
- Synthetic LLM model benchmark script
- LM Studio native benchmark mode with Qwen reasoning disabled
- First source-cited analysis smoke
- Claim persistence foundation
- Claim review workflow foundation
- First generalized analysis module endpoint; active modules are now `search_findings` and downstream `detect_contradiction_candidates`
- Event persistence foundation with `events` and `event_sources`
- Historical `extract_events` module foundation; the raw event extraction module has since been retired
- Case review report API for claim/event/source/review overview
- JSON export bundle foundation for review reports
- HTML review report export foundation with escaping
- Export review workflow foundation
- Event review workflow foundation
- Shared review service helper for claim/event/export review logic
- Entity persistence foundation with `entities` and `entity_mentions`
- Historical `extract_entities` module foundation; the raw entity extraction module has since been retired
- Entity review workflow foundation
- Case review report filtering by object type, review status, and source validation status
- Review report export filters
- Expanded review report source details with document metadata, offsets, chunk/page metadata, and bounded source excerpts
- Analysis module service split into common helpers, finding search, and downstream contradiction detection services
- Analysis module retrieval fallback for broader natural-language Hungarian prompts
- Historical `summarize_case` smoke passed before summary items and the raw summary module were retired
- Contradiction candidate persistence, source linkage, API, review workflow, and review report inclusion
- Manual contradiction candidates can be corrected by detaching their A/B input claim side; corrected partial candidates remain explicit, audited, and deletable instead of disappearing as claim-deletion side effects
- AI-asszisztens module foundation with saved local LLM chat history, soft delete, rename, generic LM Studio message calls, and a stable token-aligned chat UI independent from case/RAG/object workflows
- Shared tokenized confirmation dialog layer for destructive confirmations and typed-name deletion flows, replacing browser-native confirm/prompt popups
- `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs
- Live `detect_contradiction_candidates` smoke passed on a two-claim time conflict sample
- `detect_contradiction_candidates` now treats fewer than two source-valid claims as a clean warning precondition and records claim-selection metadata in the analysis run
- `detect_contradiction_candidates` now uses deterministic backend-selected claim pairs with pair limits, meaningful focus filtering, selected-pair audit metadata, and validation against unselected pair references
- Contradiction candidate output is normalized before persistence: same pair/type duplicates are skipped, most model-proposed `high` severities are capped to `medium`, and titles/descriptions are conservative pair-bound text from selected source-cited claims
- `detect_contradiction_candidates` supports claim review scope; the default excludes rejected claims
- `detect_contradiction_candidates` requires explicit contradiction qualification before persistence; contextual but non-conflicting pairs are not saved as contradiction candidates
- Repeated analysis runs skip already persisted, content-matched review outputs for currently supported structured review objects instead of creating duplicate review objects
- Entity extraction automatically merges only exact/normalized repeated entities into the existing entity review object and links additional occurrences as mentions/sources
- Ambiguous entity identity decisions are handled through the explicit entity merge workflow, not by automatic alias guessing
- Claim/entity/event/missing item candidate merge controls are available on report item cards and the object detail panel where applicable; target choices come from the full case object lists
- Merge, source move, source detach, and detached-source reattach remain constrained to the same main object type, but subtype matching is intentionally not enforced
- Claim/entity/event/missing item candidate source links can be detached manually from source details through audit-tracked `detach_source` review actions
- Detached source links are parked with source/object snapshots and shown in the frontend under `Levalasztott forrasok`
- Parked detached sources can be reattached or marked irrelevant; source details can also move a source directly to another same-main-type target object
- Users can select readonly text from document chunks and create source-bound manual claim/entity/event/missing item candidate objects through `manual_entry` provenance runs
- Detached source items can also be used as the source for new manual claim/entity/event/missing item candidate objects
- Missing item candidate persistence, source linkage, API, review workflow, and review report inclusion
- Missing item candidate structured object support remains available through manual/finding-conversion workflows
- Historical `detect_missing_items` smoke passed before the raw missing-item module was retired
- Missing item candidate JSON/HTML export smoke coverage
- Analysis retrieval fallback improved for short/inflected Hungarian queries such as `mellekletet`
- Source-bound finding search requires explicit focus text and fails clearly when retrieval finds no matching source chunk, avoiding blind processing on large cases
- Local chunk indexing through LM Studio/OpenAI-compatible embeddings and Qdrant, with `embed_chunks` analysis run provenance
- Explicit LM Studio embedding model load workflow; the default local embedding model is `text-embedding-bge-m3`
- Current embedding load profile uses `text-embedding-bge-m3` with `context_length=4096`; previous Qwen embedding defaults are retired
- Model-specific Qdrant chunk collections, so switching embedding models does not mix vector dimensions
- Batched embedding index creation through `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE` to avoid oversized LM Studio embedding requests
- Background chunk indexing with frontend progress polling, so larger LM Studio/Qdrant indexing work does not depend on one long HTTP request
- Chunk index readiness and latest-run progress status for the configured embedding model, surfaced in the frontend before semantic/hybrid analysis runs and scoped to the current selected document or structured case-scope document subset
- Keyword/semantic/hybrid retrieval for `search_findings` across selected-document and whole-case source scopes
- Minimal React/Vite workbench frontend scaffold
- Frontend review actions for review report items
- Frontend source detail and review history display for report items
- Frontend long-running operation feedback with elapsed time and last action summary
- Frontend document list and analysis run history views
- Frontend document page/chunk and analysis run input/output drill-down with human-readable selected-source and output summaries
- Frontend TXT/PDF import selection and OCR action for review-required/no-page PDF documents
- Frontend source scope controls for `search_findings`
- Frontend import/detail/analysis taxonomy controls, backend taxonomy API/filter workflows, and DB/search-entry taxonomy columns have been retired; large-case source narrowing now moves toward concrete document selection, focus text, and retrieval strategy
- Document lifecycle controls for active/excluded/archived documents, plus safe early discard for documents that have not yet become analysis/source material
- Active-document gate for new indexing, retrieval, analysis, source-reference creation, manual source-bound object creation, detached-source reattachment, source movement, merge workflows, and contradiction candidate creation
- Frontend optional-focus and claim-review-scope claim-pair display for contradiction analysis, contradiction analysis run details, and conservative contradiction review notes
- Frontend analysis focus input starts empty; examples are placeholders only and are not processed unless the user types text
- Frontend review status/source validation filters and object detail panel
- Frontend export history and review report filter controls
- Manual contradiction candidate UI from two source-valid, non-rejected claims with readonly claim/source previews
- Frontend visible text localized to Hungarian with labels for backend enum/internal values
- End-to-end frontend/API smoke history covers case creation, TXT import, review queue filtering, claim review, JSON export, export history backing endpoint, download, and Vite proxy
- Source-bound `Kutatási találatok` workflow: `search_findings` creates source-cited research worklist items, users can set aside/restore/delete/bulk-delete them, and selected findings can be converted into structured claim/entity/event/missing item candidate objects
- Full-case deletion through `Ügy végleges törlése`, preserving global audit history while removing case-owned rows, files, and Qdrant points
- Full-document processing surface: selected active document plus page range can create backend source-evidence-validated person-search `document_processing_items`; users can switch between active/félretett views, restore set-aside items, filter by item name, mark one or all visible items for deletion, bulk-delete marked items, see repeated-label tags, and hand a recommended focus back to the `Ügy munkapad`
- Full-document `Szabad iratkérdés` profile: selected active document pages plus a one-line user question create persistent `full_document_answers`, shown in an `Iratválasz` panel separate from the person worklist, with saved-answer switching/deletion, automatic list refresh after deletion, safe Markdown rendering, and tolerant answer JSON recovery when `answer_text` is salvageable
- Iratgyűjtemények: users can create source-scope collections, preview active-document scope resolution, select a target collection in the `Iratok` panel, mark individual or all visible documents, bulk-add marked batches, inspect collection contents, search within collection members, and bulk-remove marked documents without duplicating source documents
- Retired raw chunk extraction modules (`extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, `detect_missing_items`) are no longer active backend/frontend workflows

PDF/OCR sample checks:

- Generate samples: `.venv/bin/python scripts/generate_pdf_samples.py`
- Evaluate samples: `.venv/bin/python scripts/evaluate_pdf_samples.py`

Next:

- Treat the dedicated `Tudásbázis` module as a stable first baseline: Markdown (`.md`) documents are imported and queried as structured knowledge-base material, not as investigative case files (`Design_documents/21_markdown_knowledge_base_module_plan.md`)
- The current `Tudásbázis` baseline includes global `knowledge_base` / `markdown_note` storage, Marko/AST Markdown parsing/chunking, separate knowledge indexing/querying, archive/restore/final-delete lifecycle controls, batch-only Markdown import with conflict preview/decision handling, Markdown-rendered answers, lazy full-source inspection, and the accepted Markdown-aware retrieval/packing behavior from `Design_documents/23_markdown_knowledge_retrieval_hardening_plan.md` and `Design_documents/24_markdown_section_aware_retrieval_packing_plan.md`
- The current larger planned development slice is the `Kapcsolati térkép` work surface from `Design_documents/25_relationship_map_graph_view_plan.md` and `Design_documents/27_relationship_map_graph_implementation_plan.md`: the data/relationship-read-only graph baseline now uses the multi-focus POST endpoint and frontend checkbox selection over source-valid structured objects, supports temporary non-persisted node repositioning, has the accepted static inspector/card styling plus subtle object-type node background colors, and the technical baseline is complete; next graph work is live readability tuning and only then larger expansions such as whole-case graph views
- Keep the dedicated `Audit naplo` API/panel backed by `audit_events` as a later larger work surface after the graph-view slice unless explicitly reprioritized
- Add multi-collection source scopes only where analysis/RAG/knowledge-base workflows need them; the current first analysis/indexing integration uses one selected collection at a time
- Keep `search_findings`, full-document person seeds, source validation, and contradiction detection as strict auditable workbench workflows beside the freer RAG question-answering layer
- Treat a serious `Jogszabályi kereső` as a later specialized module with law/section/paragraph/effective-date semantics, not as a small mode inside generic RAG
- Continue live-test driven hardening for the implemented `Általános iratkérdező`, full-document person profile, and responsive UI layers as concrete issues appear
- Treat the first `Szabad iratkérdés` full-document slice as implemented baseline: `Design_documents/29_full_document_free_question_plan.md` records the design, and the code now uses a separate `full_document_answers` workflow over selected document pages rather than another `document_processing_items` profile. Current UX hardening includes previous-answer choice buttons, refreshed answer lists after deletion, and a placeholder state for empty answer history.
- Keep documentation cleanup around retired raw modules opportunistic; active capability lists should continue to point to `search_findings`
- Consider durable job supervision if indexing grows beyond FastAPI background tasks

Frontend dev URL:

- Start infrastructure from the repo root: `docker compose up -d`
- For an interactive terminal, start backend from the repo root: `.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- For an interactive terminal, start frontend from `frontend/`: `npm run dev`
- When running, open `http://localhost:5173`; Vite proxies `/api` to `http://127.0.0.1:8000`.
- When Codex starts backend/frontend from a non-interactive WSL command, use `setsid -f` so the processes survive shell cleanup:
  - backend: `setsid -f sh -c ".venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/boberdetective-backend.log 2>&1 < /dev/null"`
  - frontend: `setsid -f sh -c "npm --prefix frontend run dev -- --host 0.0.0.0 > /tmp/boberdetective-frontend.log 2>&1 < /dev/null"`
  Verify with `ss -ltnp | grep -E ":(8000|5173)"`, `curl -fsS http://127.0.0.1:8000/api/v1/system/health`, and `curl -I http://127.0.0.1:5173`.

## Design documents

See:

- `Design_documents/00_project_context_for_codex.md`
- `Design_documents/01_concept_and_mvp_requirements.md`
- `Design_documents/02_technical_architecture_v1.md`
- `Design_documents/03_database_schema_v1.md`
- `Design_documents/03a_database_schema_pre_implementation_review.md`
- `Design_documents/04_runtime_and_deployment_v1.md`
- `Design_documents/05_api_design_v1.md`
- `Design_documents/06_document_processing_pipeline_v1.md`
- `Design_documents/07_prompt_and_json_schema_collection_v1.md`
- `Design_documents/08_mvp_backlog_and_implementation_sequence.md`
- `Design_documents/09_environment_verification_and_security_baseline.md`
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
- `Design_documents/21_markdown_knowledge_base_module_plan.md`
- `Design_documents/22_markdown_ast_chunking_plan.md`
- `Design_documents/23_markdown_knowledge_retrieval_hardening_plan.md`
- `Design_documents/24_markdown_section_aware_retrieval_packing_plan.md`
- `Design_documents/25_relationship_map_graph_view_plan.md`
- `Design_documents/26_review_report_status_cleanup_plan.md`
- `Design_documents/27_relationship_map_graph_implementation_plan.md`
- `Design_documents/28_relationship_map_horizontal_layout_plan.md`
- `Design_documents/29_full_document_free_question_plan.md`

## Handoff notes

For future Codex sessions, read:

- `AGENTS.md`
- `AI_NOTES.md`
- `CURRENT_STATE.md`
- `CHANGELOG.md`

`CURRENT_STATE.md` is the short fresh-session handoff. It records the current verification baseline, API inventory, smoke workflow, and next logical steps.

## Current implementation

Initial backend scaffold exists under `app/` with:

- FastAPI app factory
- `/api/v1/system/health`
- secure config loader
- JSONL audit writer skeleton
- storage path resolver with path traversal protection
- SQLAlchemy/psycopg DB layer
- Alembic migration foundation through `0042_doc_proc_person_only`
- `users`, `cases`, `case_users`, `audit_events` tables
- case create/list API
- DB + JSONL audit on case creation
- `documents`, `document_pages`, `document_chunks` tables
- immutable TXT import API with DB + JSONL audit
- deterministic TXT chunk creation during import
- document chunks API
- document lifecycle API for archive/exclude/restore and safe early discard
- keyword search API over document pages/chunks
- source-reference API with quote validation
- `/api/v1/system/llm/smoke` endpoint for local provider reachability
- `analysis_runs`, `analysis_run_inputs`, and `analysis_run_outputs` tables
- analysis run list/detail API
- `scripts/run_llm_benchmark.py` for local model comparison
- source-cited analysis smoke API with Qwen native reasoning-off
- `claims` and `claim_sources` persistence with source reference linkage
- `human_reviews` append-only review history for claims
- generalized `POST /api/v1/cases/{case_id}/analysis/modules/{module_key}` endpoint, currently supporting `search_findings` and `detect_contradiction_candidates`
- source-bound finding search with `case` and `document` source modes plus required focus text and chunk batch metadata
- active module-specific analysis services under `app/services/analysis_module_findings.py` and `app/services/analysis_module_contradictions.py`
- entity list/detail API
- entity review API with append-only human review history
- `events` and `event_sources` persistence with source reference linkage
- event list/detail API
- event review API with append-only human review history
- case review report API at `GET /api/v1/cases/{case_id}/review-report` with optional `object_type`, `review_status`, and `source_validation_status` filters plus expanded source details
- JSON/HTML review report export API with claim/entity/event item tracking, optional `report_filters`, expanded source details, and download endpoint
- contradiction candidate list/create/detail/review API
- export review API with append-only human review history
- shared review helper used by claim, entity, event, and export review workflows
- pytest smoke tests

Development services:

- PostgreSQL: `127.0.0.1:5432`
- Qdrant: `127.0.0.1:6333`

Frontend:

- React/Vite scaffold under `frontend/`
- Dev server: `cd frontend && npm run dev`
- API proxy: `/api` -> `http://127.0.0.1:8000`
- Current UI workflows: case create/list, multi-file TXT/PDF import without import-time taxonomy selection, document list, document lifecycle actions, page/chunk drill-down, OCR recommendation, explicit PDF text review and chunk creation, analysis run with elapsed-time feedback, analysis history/detail, review report filtering by object/review/source status, object detail inspection, source detail inspection, review history, review actions, manual source-bound object creation, manual contradiction candidate creation, JSON/HTML export, export history
- Active `search_findings` UI supports selected-document and whole-case source scopes with required focus text, `Szovegresz plafon` defaulting to 45 and capped at 90, retrieval strategy, and batch controls. Selected-document mode searches the full selected document.
- Raw-chunk analysis can choose keyword, semantic, or hybrid source retrieval after chunk indexing
