# AGENTS.md

## Project

Local Investigative Document Intelligence System

Hungarian working name:

```text
Lokális Nyomozati Iratintelligencia Rendszer
```

## What This Repository Is

This repository currently contains design documents for a future fully local, auditable investigative document intelligence system.

There is no application implementation yet.

The system is intended to process large collections of investigative, legal, evidentiary, or case-related documents and produce structured, source-cited, human-reviewable outputs.

## Core Rule

The language model is not the source of truth.

Sources of truth are:

- original documents,
- extracted page-level text,
- source references,
- audit logs,
- human review decisions.

Mandatory rule:

```text
No source -> no claim.
```

Every AI-generated object must be traceable to:

- concrete source documents/pages/chunks,
- the analysis run that created it.

## What The System Must Not Do

The system must not:

- make autonomous legal, investigative, or personal decisions,
- accuse or identify suspects automatically,
- determine guilt or innocence,
- perform predictive policing,
- score people by risk,
- replace investigators, prosecutors, judges, defenders, or experts,
- treat LLM output as verified fact.

## Current Technical Direction

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

NLP:

- HuSpaCy
- regex-based extraction rules

Frontend:

- React

Runtime/deployment:

- Windows 11 host as workstation/editor/browser environment
- WSL2 Ubuntu as the main application runtime
- LM Studio running natively on the Windows 11 host as the default development LLM provider
- Backend accesses LM Studio through a local OpenAI-compatible API
- LLMProvider abstraction must allow later replacement with Ollama, llama.cpp / llama-server, or another local runtime

## Working Environment Assumptions

The user is moving the project from a Windows path into a dedicated WSL2 Ubuntu environment.

Target WSL-side project path:

```text
~/projects/Codex_BoberDetective
```

Target WSL-side data path:

```text
~/boberdetective-data
```

Use VS Code Remote WSL by opening the project from inside WSL:

```bash
cd ~/projects/Codex_BoberDetective
code .
```

When running shell commands from Codex, use explicit WSL context:

```powershell
wsl -d Ubuntu-24.04 -u bober sh -lc 'cd /home/bober/projects/Codex_BoberDetective && <command>'
```

Do not rely on plain `wsl`, because Windows may default to another WSL distribution.

Assumption:

The current Windows-side files may be copied manually by the user into the WSL-side project path before the next implementation session.

## Important Documents To Read First

Read these before making plans or edits:

- `README.md`
- `AI_NOTES.md`
- `CURRENT_STATE.md`
- `CHANGELOG.md`, if present
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

## Editing Guidance

- Do not start implementation until the user explicitly asks for it.
- Preserve the design-first workflow.
- Keep source traceability and auditability central in all designs.
- Do not introduce cloud dependencies.
- Do not make the system chatbot-first.
- Treat it as a case analysis workbench.
- Avoid changing `README.md` heavily; small link/status updates are acceptable.
- Do not create `TODO.md`; keep next steps in `AI_NOTES.md`.
- Keep the fresh-session quick-start state in `CURRENT_STATE.md`.
- Keep user-facing frontend text in Hungarian. Internal API keys and enum values may remain English, but visible labels, buttons, placeholders, status text, and empty states should be shown with Hungarian labels.

## Current State

As of the latest handoff:

- Concept and MVP requirements are complete.
- Technical architecture v1 is complete.
- Database schema v1 is drafted and updated with the pre-implementation review refinements.
- Database schema pre-implementation review is drafted.
- Runtime and deployment v1 is drafted.
- API design v1 is drafted.
- Document processing pipeline v1 is drafted.
- Prompt and JSON schema collection v1 is drafted.
- MVP backlog and implementation sequence is drafted.
- Environment verification and security baseline is drafted.
- Initial source code implementation exists:
  - Python/FastAPI scaffold,
  - health endpoint,
  - config loader,
  - JSONL audit writer skeleton,
  - secure storage path resolver,
  - SQLAlchemy/psycopg DB layer,
  - Alembic migration foundation,
  - migrations through `0016_manual_entry`,
  - users/cases/case_users/audit_events tables,
  - documents/pages/chunks/source references,
  - analysis runs and source-cited analysis modules,
  - claims/events/entities/summary items/contradiction candidates/missing item candidates,
  - case create/list API,
  - TXT import, native-text PDF import, explicit OCR for PDF documents, keyword search, review report, JSON/HTML exports,
  - pytest smoke tests.

Current implementation caveats:

- Git repository is initialized on branch `main` and tracks `origin/main`.
- Docker is installed and `bober` can access the Docker socket.
- PostgreSQL and Qdrant run through Docker Compose.
- PostgreSQL is reachable at `127.0.0.1:5432`.
- Qdrant is reachable at `127.0.0.1:6333`.
- LM Studio is reachable from WSL at `http://127.0.0.1:1234/v1`.
- Configured chat-model load profile is `context_length=12288`, `eval_batch_size=6144`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`; chat model loading uses `POST /api/v1/system/llm/load-chat-model`.
- Configured embedding model defaults to `text-embedding-qwen3-embedding-4b@q6_k`; embedding model loading uses `POST /api/v1/system/llm/load-embedding-model` with `context_length=12288`, and embedding calls auto-ensure the configured model is loaded before `/v1/embeddings`. LM Studio currently rejects `eval_batch_size`, `flash_attention`, and `offload_kv_cache_to_gpu` for embedding models, so those are intentionally not sent for embedding load.
- LM Studio native chat calls auto-ensure the configured chat model is loaded; they reuse a matching loaded instance id or load the model with the configured profile when missing.
- Latest test run: `171 passed`.
- Latest Alembic state: `0016_manual_entry (head)`.
- Native-text PDF import uses configurable `BOBERDETECTIVE_PDF_PARSER`; the default `docling_then_pypdf` profile prefers Docling and falls back to local `pypdf`.
- Docling is installed in `.venv`; explicit `BOBERDETECTIVE_PDF_PARSER=docling` import smoke passed with parser `docling` and `parse_document` validation `passed`.
- Tesseract OCR foundation exists for PDF documents through `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr`.
- Image-only/scanned PDFs without native text remain importable as audit-tracked `review_required` documents so the explicit OCR path can process them.
- OCR test coverage includes a generated scanned-style/image-only PDF fixture; native parsing reports no source text, then Tesseract extracts OCR text.
- Synthetic PDF samples are generated under `samples/pdf/` by `scripts/generate_pdf_samples.py`; `scripts/evaluate_pdf_samples.py` evaluates native parse, OCR text length, confidence, and quality issues.
- OCR now stores average Tesseract confidence when available and flags low-confidence OCR pages as `low_ocr_confidence`.
- Document page API returns OCR confidence as a numeric value and handles Decimal-backed DB values.
- Default upload limit is 50 MiB through `BOBERDETECTIVE_MAX_UPLOAD_BYTES`.
- Analysis batch processing is planned in `Design_documents/10_analysis_batch_processing_plan.md`; raw-chunk analysis modules are batch-capable while preserving focused query mode.
- `extract_events` caps its effective batch size at 2 chunks for local LLM stability even when the requested UI/API batch size is higher; latest semantic live regression with query `gyilkossággal esettel kapcsolatos események`, `limit=10`, and requested `batch_size=5` completed without timeout in about 262s.
- `detect_contradiction_candidates` is intentionally claim-pair based rather than raw chunk batch-based; it records claim-selection and selected-pair metadata, returns a warning without LLM execution when fewer than two source-valid claims or no selected pairs exist, and rejects model output that references unselected claim pairs.
- Contradiction candidate output is normalized before persistence: same pair/type duplicates are skipped, most model-proposed `high` severities are capped to `medium`, and titles/descriptions are deterministic conservative text based on the selected source-cited claim pair.
- Contradiction detection supports `claim_review_scope`; default `reviewable` excludes rejected claims and includes source-valid `new`, `needs_review`, `verified`, and `corrected` claims.
- Contradiction detection requires explicit qualification before persistence: `is_contradiction_candidate=true` and a concrete `conflict_basis`; contextual/non-conflicting pairs should become unsupported items, not saved candidates.
- Repeated analysis runs now skip already persisted, content-matched review outputs for claims, events, summary items, missing item candidates, and contradiction candidates instead of creating duplicate review objects.
- Entity extraction automatically merges only exact/normalized repeated entities into the existing entity review object and links additional occurrences as mentions/sources.
- Ambiguous entity identity decisions should be handled through the explicit entity merge workflow, not by automatic alias guessing.
- Frontend entity merge controls are available on report item cards and the object detail panel; target choices come from the full case entity list.
- Event merge follows the same human-reviewed pattern, with target choices from the full case event list.
- Missing item candidate merge follows the same human-reviewed pattern, with target choices from the full case missing item candidate list.
- Entity, event, and missing item candidate source links can be manually detached through audit-tracked `detach_source` review actions; review report sources expose the concrete source-link id needed for this, and detached links are parked in `detached_source_items` with object/source snapshots.
- Detached sources can be reattached from the `Levalasztott forrasok` panel or marked irrelevant; source details also support direct source move to another same-type target object without a manual detach/reattach round.
- Users can create source-bound manual objects from selected document chunk text through `manual_entry` provenance runs; the selected quote is read-only in the frontend and revalidated by the backend source-reference flow.
- Detached source items can also be used as the source for new manual claim/entity/event/missing item candidate objects, then marked handled with the created object target.
- Manual contradiction candidates can be created from two source-valid, non-rejected claims through a dedicated `Kezi ellentmondasjelolt` panel; selected claim text and sources are shown as read-only previews and the created candidate is tracked through `manual_entry` analysis run provenance.
- Latest live analysis smoke: `detect_missing_items` produced 2 source-cited `attachment` candidates and review report inclusion.
- Latest export smoke: missing item candidates are included in JSON/HTML review report exports with tracked export items.
- Latest retrieval smoke: `Keress hivatkozott mellekletet.` now succeeds after Hungarian suffix fallback tuning.
- Latest frontend/API smoke: live backend plus Vite dev server passed case creation, TXT import, all MVP analysis modules, review queue filter, claim review, JSON export/list/download, frontend index, and `/api` proxy.
- Minimal React/Vite frontend scaffold exists under `frontend/`.
- Frontend review actions exist for review report items through allowlisted API paths.
- Frontend report items show source details and review history.
- Frontend shows long-running operation feedback with elapsed time and last action summary.
- Frontend shows selected-case document list and analysis run history.
- Frontend shows document page/chunk and analysis run input/output drill-down.
- Frontend shows contradiction claim-selection metadata as Hungarian claim-pair summaries in analysis run details, exposes claim review scope in the contradiction analysis panel, and marks contradiction report items as review-only candidates rather than proven facts.
- Frontend review report supports object/review/source filters and selected object detail.
- Frontend shows export history; review report filtering is handled through object/review/source dropdown filters.
- Frontend visible labels are localized to Hungarian; keep future UI text Hungarian and map backend enum/internal values before displaying them.
- Latest frontend verification: `npm run build` passed.

Strategic next direction:

- Continue hardening the backend analysis foundation rather than deep frontend polishing.
- Retrieval/indexing foundation has started: chunk indexing uses local LM Studio/OpenAI-compatible embeddings plus model-specific Qdrant collections, skips only chunks indexed with the currently configured embedding model, and focused-query raw-chunk analysis modules can request `keyword`, `semantic`, or `hybrid` retrieval.
- Embedding index creation uses `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE` defaulting to `8`; keep it conservative on the current 32 GB workstation to avoid LM Studio timeout/RAM spikes.
- Background chunk indexing is exposed through `POST /api/v1/cases/{case_id}/indexes/chunks/jobs`; it creates an `embed_chunks` analysis run and returns immediately while FastAPI `BackgroundTasks` performs the embedding/Qdrant work.
- Chunk index readiness is exposed through `GET /api/v1/cases/{case_id}/indexes/chunks/status`; frontend semantic/hybrid runs are blocked until the active source scope is fully indexed with the configured embedding model, and the same status response exposes latest-run input/output progress.
- Latest Qwen3 embedding smoke loaded `text-embedding-qwen3-embedding-8b`, reindexed 49 chunks from the Morgue PDF into `boberdetective_chunks_text_embedding_qwen3_embedding_8b`, returned semantic hybrid-search hits, and a focused `extract_claims` run recorded hybrid/semantic retrieval provenance. The current configured embedding default has since been reduced to `text-embedding-qwen3-embedding-4b@q6_k`; reindex before comparing new retrieval results.
- Latest empty-state model-load smoke accepted the current reduced profile: `text-embedding-qwen3-embedding-4b` loaded in 3.461s and `qwen/qwen3.5-9b` loaded in 16.942s with `eval_batch_size=6144`.
- Latest 4B embedding reindex smoke succeeded with `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE=8`: 49 Morgue PDF chunks were indexed into `boberdetective_chunks_text_embedding_qwen3_embedding_4b` in about 120s.
- Latest background indexing smoke succeeded: a 16-chunk forced Morgue PDF reindex returned immediately, status polling showed `0/16 -> 8/16 -> 16/16`, and the run finished `succeeded` / `passed`.
- User-side semantic/hybrid retrieval smoke after switching to `text-embedding-qwen3-embedding-4b@q6_k` found no obvious quality regression so far.
- Next target should be retrieval ranking calibration, document/case source-mode hybrid selection, and frontend visibility into selected source chunks. Keep source provenance and `no source -> no claim` central.
- Frontend work in this phase should only support the backend workflow: source scope, optional focus, batch limits, Hungarian labels, and clear status/error feedback.
- Rationale: raw-chunk modules can now process document/case scopes, while contradiction detection should operate downstream from source-cited claims and keep `no source -> no claim` intact.

## Security Baseline

Implement code with secure-by-default practices:

- parameterized SQL / ORM, no string-built SQL from user input,
- no raw rendering of user/document/LLM content as HTML,
- no user-controlled template execution,
- avoid shell calls; if unavoidable, use argument lists and no shell,
- constrain all file operations to the configured data root,
- treat LLM output as untrusted and schema/source-validate it,
- do not log secrets or full environment dumps.
