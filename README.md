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
- Analysis run provenance foundation
- Synthetic LLM model benchmark script
- LM Studio native benchmark mode with Qwen reasoning disabled
- First source-cited analysis smoke
- Claim persistence foundation
- Claim review workflow foundation
- First generalized analysis module endpoint with `extract_claims`
- Event persistence foundation with `events` and `event_sources`
- `extract_events` analysis module foundation
- Case review report API for claim/event/source/review overview
- JSON export bundle foundation for review reports
- HTML review report export foundation with escaping
- Export review workflow foundation
- Event review workflow foundation
- Shared review service helper for claim/event/export review logic
- Entity persistence foundation with `entities` and `entity_mentions`
- `extract_entities` analysis module foundation
- Entity review workflow foundation
- Case review report filtering by object type, review status, and source validation status
- Review report export filters
- Expanded review report source details with document metadata, offsets, chunk/page metadata, and bounded source excerpts
- Analysis module service split into common helpers and claim/event/entity/summary module-specific services
- Summary item persistence, source linkage, API, review workflow, and review report inclusion
- `summarize_case` analysis module foundation for source-cited summary item creation
- Analysis module retrieval fallback for broader natural-language Hungarian prompts
- Live `summarize_case` smoke passed with the original broad query after retrieval fallback
- Contradiction candidate persistence, source linkage, API, review workflow, and review report inclusion
- `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs
- Live `detect_contradiction_candidates` smoke passed on a two-claim time conflict sample
- `detect_contradiction_candidates` now treats fewer than two source-valid claims as a clean warning precondition and records claim-selection metadata in the analysis run
- `detect_contradiction_candidates` now uses deterministic backend-selected claim pairs with pair limits, meaningful focus filtering, selected-pair audit metadata, and validation against unselected pair references
- Contradiction candidate output is normalized before persistence: same pair/type duplicates are skipped, most model-proposed `high` severities are capped to `medium`, and titles/descriptions are conservative pair-bound text from selected source-cited claims
- `detect_contradiction_candidates` supports claim review scope; the default excludes rejected claims
- `detect_contradiction_candidates` requires explicit contradiction qualification before persistence; contextual but non-conflicting pairs are not saved as contradiction candidates
- Repeated analysis runs skip already persisted, content-matched review outputs for claims, events, summary items, missing item candidates, and contradiction candidates instead of creating duplicate review objects
- Entity extraction automatically merges only exact/normalized repeated entities into the existing entity review object and links additional occurrences as mentions/sources
- Ambiguous entity identity decisions are handled through the explicit entity merge workflow, not by automatic alias guessing
- Entity merge controls are available on report item cards and the object detail panel; target choices come from the full case entity list
- Event merge follows the same human-reviewed pattern, with target choices from the full case event list
- Missing item candidate merge follows the same human-reviewed pattern, with target choices from the full case missing item candidate list
- Entity/event/missing item candidate source links can be detached manually from source details through audit-tracked `detach_source` review actions
- Detached source links are parked with source/object snapshots and shown in the frontend under `Levalasztott forrasok`
- Parked detached sources can be reattached or marked irrelevant; source details can also move a source directly to another same-type target object
- Users can select readonly text from document chunks and create source-bound manual claim/entity/event/missing item candidate objects through `manual_entry` provenance runs
- Detached source items can also be used as the source for new manual claim/entity/event/missing item candidate objects
- Missing item candidate persistence, source linkage, API, review workflow, and review report inclusion
- `detect_missing_items` analysis module foundation over source-cited chunk quotes
- Live `detect_missing_items` smoke passed on referenced attachment/photo documentation sample
- Missing item candidate JSON/HTML export smoke coverage
- Analysis retrieval fallback improved for short/inflected Hungarian queries such as `mellekletet`
- Raw-chunk analysis modules now require explicit focus text and fail clearly when retrieval finds no matching source chunk, avoiding blind processing on large cases
- Local chunk indexing through LM Studio/OpenAI-compatible embeddings and Qdrant, with `embed_chunks` analysis run provenance
- Explicit LM Studio embedding model load workflow; the default local embedding model is `text-embedding-qwen3-embedding-4b@q6_k`
- Model-specific Qdrant chunk collections, so switching embedding models does not mix vector dimensions
- Batched embedding index creation through `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE` to avoid oversized LM Studio embedding requests
- Background chunk indexing with frontend progress polling, so larger LM Studio/Qdrant indexing work does not depend on one long HTTP request
- Chunk index readiness and latest-run progress status for the configured embedding model, surfaced in the frontend before semantic/hybrid analysis runs and scoped to the current selected document or structured case-scope document subset
- Keyword/semantic/hybrid retrieval for batch-capable raw-chunk analysis modules across selected-document and whole-case source scopes
- Minimal React/Vite workbench frontend scaffold
- Frontend review actions for review report items
- Frontend source detail and review history display for report items
- Frontend long-running operation feedback with elapsed time and last action summary
- Frontend document list and analysis run history views
- Frontend document page/chunk and analysis run input/output drill-down with human-readable selected-source and output summaries
- Frontend TXT/PDF import selection and OCR action for review-required/no-page PDF documents
- Frontend source scope controls for batch-capable raw-chunk analysis modules
- Frontend structured document taxonomy controls for import/list display and whole-case analysis source filtering by document group, document type, and selected document list
- Document lifecycle controls for active/excluded/archived documents, plus safe early discard for documents that have not yet become analysis/source material
- Active-document gate for new indexing, retrieval, analysis, source-reference creation, manual source-bound object creation, detached-source reattachment, source movement, merge workflows, and contradiction candidate creation
- Frontend optional-focus and claim-review-scope claim-pair display for contradiction analysis, contradiction analysis run details, and conservative contradiction review notes
- Frontend analysis focus input starts empty; examples are placeholders only and are not processed unless the user types text
- Frontend review status/source validation filters and object detail panel
- Frontend export history and review report filter controls
- Manual contradiction candidate UI from two source-valid, non-rejected claims with readonly claim/source previews
- Frontend visible text localized to Hungarian with labels for backend enum/internal values
- End-to-end frontend/API smoke passed through case creation, TXT import, all MVP analysis modules, review queue filter, claim review, JSON export, export history backing endpoint, download, and Vite proxy
- Source-bound `Kutatási találatok` workflow: `search_findings` creates source-cited research worklist items, users can set aside/restore/delete/bulk-delete them, and selected findings can be converted into structured claim/entity/event/missing item candidate objects

PDF/OCR sample checks:

- Generate samples: `.venv/bin/python scripts/generate_pdf_samples.py`
- Evaluate samples: `.venv/bin/python scripts/evaluate_pdf_samples.py`

Next:

- Cleanly retire the still-present raw chunk-based automatic extraction modules according to `Design_documents/13_legacy_analysis_module_retirement_plan.md`
- After the legacy module removal is clean, design and implement a full `Audit naplo` API/panel backed by `audit_events`, separate from the current `analysis_runs`-based processing/run history
- Consider durable job supervision if indexing grows beyond FastAPI background tasks

Frontend dev URL:

- Start backend from the repo root: `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Start frontend from `frontend/`: `npm run dev`
- When running, open `http://localhost:5173`; Vite proxies `/api` to `http://127.0.0.1:8000`.
- When Codex starts the frontend as a background process from a non-interactive WSL command, use `setsid` so Vite survives shell cleanup:
  `setsid sh -c "npm --prefix frontend run dev -- --host 0.0.0.0 > /tmp/boberdetective-frontend.log 2>&1" < /dev/null &`
  If `localhost:5173` is unreachable, first check inside WSL with `ss -ltnp | grep 5173`; a previous failure mode was Vite logging `ready`, then exiting with `Hangup`.

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
- Alembic migration foundation through `0024_research_findings_worklist`
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
- `detect_missing_items` analysis module with quote validation, source-reference creation, missing-item candidate persistence, and analysis run provenance
- source-cited analysis smoke API with Qwen native reasoning-off
- `claims` and `claim_sources` persistence with source reference linkage
- `human_reviews` append-only review history for claims
- generalized `POST /api/v1/cases/{case_id}/analysis/modules/{module_key}` endpoint, currently supporting `extract_claims`, `extract_events`, `extract_entities`, and `summarize_case`
- batch-capable raw-chunk analysis modules with `case` and `document` source modes plus required focus text and chunk batch metadata
- module-specific analysis services under `app/services/analysis_module_*.py`
- entity list/detail API
- entity review API with append-only human review history
- `extract_entities` analysis module
- `events` and `event_sources` persistence with source reference linkage
- event list/detail API
- event review API with append-only human review history
- `extract_events` analysis module
- case review report API at `GET /api/v1/cases/{case_id}/review-report` with optional `object_type`, `review_status`, and `source_validation_status` filters plus expanded source details
- JSON/HTML review report export API with claim/entity/event item tracking, optional `report_filters`, expanded source details, and download endpoint
- summary item list/create/detail/review API
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
- Current UI workflows: case create/list, TXT/PDF import, document list, document taxonomy editing, document lifecycle actions, page/chunk drill-down, OCR recommendation, explicit PDF text review and chunk creation, analysis run with elapsed-time feedback, analysis history/detail, review report filtering by object/review/source status, object detail inspection, source detail inspection, review history, review actions, manual source-bound object creation, manual contradiction candidate creation, JSON/HTML export, export history
- Raw-chunk analysis module UI supports selected-document and whole-case source scopes with required focus text, selected-document page range, `Szovegresz plafon` capped at 30, and batch controls
- Raw-chunk analysis can choose keyword, semantic, or hybrid source retrieval after chunk indexing
