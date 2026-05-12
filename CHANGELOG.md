# CHANGELOG.md

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
- Updated handoff guidance so fresh sessions read `CURRENT_STATE.md` alongside the existing project notes.

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
