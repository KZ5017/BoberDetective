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
- Initial Python/FastAPI scaffold
- Docker Compose PostgreSQL/Qdrant dev runtime
- Database migration foundation
- Case and audit persistence foundation
- Document/page/chunk persistence foundation
- Immutable TXT import API
- TXT chunk creation
- Keyword search
- Source-reference foundation
- LLMProvider abstraction
- LM Studio model-list smoke endpoint
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
- Missing item candidate persistence, source linkage, API, review workflow, and review report inclusion
- `detect_missing_items` analysis module foundation over source-cited chunk quotes
- Live `detect_missing_items` smoke passed on referenced attachment/photo documentation sample
- Missing item candidate JSON/HTML export smoke coverage
- Analysis retrieval fallback improved for short/inflected Hungarian queries such as `mellekletet`
- Minimal React/Vite workbench frontend scaffold
- Frontend review actions for review report items
- Frontend source detail and review history display for report items

Next:

- Safer long-running analysis feedback in the frontend

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
- Alembic migration foundation
- `users`, `cases`, `case_users`, `audit_events` tables
- case create/list API
- DB + JSONL audit on case creation
- `documents`, `document_pages`, `document_chunks` tables
- immutable TXT import API with DB + JSONL audit
- deterministic TXT chunk creation during import
- document chunks API
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
- Current UI workflows: case create/list, TXT import, analysis run, review report filtering, source detail inspection, review history, review actions, JSON/HTML export
