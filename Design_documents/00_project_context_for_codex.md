# Project Context for Codex

## Project name

Local Investigative Document Intelligence System  
Hungarian working name: Lokális Nyomozati Iratintelligencia Rendszer

## High-level goal

This project aims to design and later implement a fully local, auditable, human-reviewed investigative document intelligence system.

The system processes large collections of investigative, legal, evidentiary or case-related documents and produces structured, source-cited outputs such as:

- document inventory,
- entity/person list,
- event timeline,
- claim list,
- contradiction candidates,
- missing item candidates,
- source-cited case summaries,
- later: legal RAG and evidence matrices.

The system must not make autonomous legal, investigative or personal decisions.

## Core principle

The language model is not the source of truth.

Sources of truth are:

- original documents,
- extracted page-level text,
- source references,
- audit logs,
- human review decisions,
- later: verified legal corpus.

Mandatory rule:

> No source → no claim.

Every AI-generated claim, event, summary item, contradiction candidate or missing item candidate must be traceable to a concrete source reference.

## What the system must NOT do

The system must not:

- automatically accuse or identify suspects,
- score persons by risk,
- perform predictive policing,
- make autonomous legal qualification,
- determine guilt or innocence,
- replace investigators, prosecutors, judges, defenders or experts,
- make procedural recommendations without human control,
- treat LLM output as verified fact.

## MVP-1 scope

> **Aktualis megjegyzes, 2026-05-17:** az alabbi lista eredeti celallapot. A tenyleges implementacio nehany ponton tudatosan finomodott: a PDF text layer mar explicit emberi ellenorzesi/chunkolas lepesen megy at, az elemzesi moduloknal a `focused_query` forraskor megszunt, a nagyobb ugyekhez pedig strukturalt irattaxonomia/forrasszures keszul. Reszletek: `Design_documents/06_document_processing_pipeline_v1.md`, `Design_documents/10_analysis_batch_processing_plan.md`, `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`.

The first MVP should focus on the investigative document processing core:

1. Case creation.
2. Document import.
3. SHA-256 file hashing.
4. PDF/DOCX/TXT text extraction.
5. OCR for scanned documents.
6. Page-level text storage.
7. Chunking.
8. Local keyword and vector indexing.
9. Source-cited search.
10. Entity/person extraction.
11. Timeline candidate generation.
12. Claim extraction.
13. Contradiction candidate generation.
14. Missing item candidate generation.
15. Audit logging.
16. Human review workflow.
17. Exportable reports.

Legal RAG is a later module and should not be implemented before the document processing and source-citation foundation is stable.

## Proposed technical stack

Backend:

- Python
- FastAPI

Database:

- PostgreSQL

Vector search:

- Qdrant

Document parsing:

- Docling

OCR:

- Tesseract OCR with Hungarian language support

Hungarian NLP:

- HuSpaCy
- regex-based extraction rules

Local LLM:

- LM Studio running natively on the Windows 11 host as the default development LLM provider
- Exposed through LM Studio's local OpenAI-compatible API
- Backend uses an LLMProvider abstraction so LM Studio can later be replaced by Ollama, llama.cpp / llama-server, or another local runtime without changing the analysis modules
- Ollama remains a supported alternative development provider
- llama.cpp / llama-server remains a strong candidate for later controlled local deployment

Frontend:

- React

Audit:

- PostgreSQL audit_events table
- append-only JSONL log

Exports:

- Markdown / HTML / JSON for MVP
- PDF / DOCX later

## Existing design documents

Read these before making plans or writing code:

1. `Design_documents/01_concept_and_mvp_requirements.md`
2. `Design_documents/02_technical_architecture_v1.md`
3. `Design_documents/03_database_schema_v1.md`
4. `Design_documents/03a_database_schema_pre_implementation_review.md`
5. `Design_documents/04_runtime_and_deployment_v1.md`
6. `Design_documents/05_api_design_v1.md`
7. `Design_documents/06_document_processing_pipeline_v1.md`
8. `Design_documents/07_prompt_and_json_schema_collection_v1.md`
9. `Design_documents/08_mvp_backlog_and_implementation_sequence.md`
10. `Design_documents/09_environment_verification_and_security_baseline.md`

## Current project state

Initial implementation has started.

We have completed:

1. Concept and MVP requirements.
2. Technical architecture v1.
3. Database schema v1 with pre-implementation refinements.
4. Runtime and deployment v1.
5. API design v1.
6. Document processing pipeline v1.
7. Prompt and JSON schema collection v1.
8. MVP backlog and implementation sequence.
9. Environment verification and security baseline.
10. Initial Python/FastAPI scaffold with health endpoint, config loader, audit writer skeleton, secure storage path resolver, and tests.
11. Docker Compose PostgreSQL/Qdrant development runtime.
12. Database migration foundation with initial users/cases/audit tables.
13. Case create/list API with DB and JSONL audit on case creation.

The next logical step is:

> Continue the first implementation sprint with document/page/chunk persistence and immutable TXT import.

## Requested next step

Begin implementation only after explicit user approval.

The first scaffold, database runtime, migration foundation, and case/audit persistence are complete. The next implementation step should build immutable document import, page/chunk source layer, and keyword search before any LLM analysis module.

Implementation has been explicitly approved by the user. Continue conservatively and keep source/audit/security constraints central.

## Design constraints

Important constraints:

1. Local-first / offline-capable.
2. No cloud dependency.
3. Sensitive-data-safe.
4. Every generated object must be source-citable.
5. Every AI analysis must be reproducible from stored inputs.
6. Every human review must be logged.
7. Original files must remain immutable.
8. AI output must be clearly separated from human-verified output.
9. Legal RAG should be anticipated but not implemented in MVP-1.
10. The system is a case analysis workbench, not a chatbot-first product.

## Preferred working style

Before writing or changing files:

1. Read the existing design documents.
2. Summarize the current architecture briefly.
3. Confirm environment readiness.
4. Then start the first implementation sprint if explicitly approved.

Use clear Markdown.
Be precise.
Prefer practical engineering decisions over theoretical discussion.
