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
  - migrations through `0012_missing_item_candidates`,
  - users/cases/case_users/audit_events tables,
  - documents/pages/chunks/source references,
  - analysis runs and source-cited analysis modules,
  - claims/events/entities/summary items/contradiction candidates/missing item candidates,
  - case create/list API,
  - TXT import, keyword search, review report, JSON/HTML exports,
  - pytest smoke tests.

Current implementation caveats:

- Git repository is initialized on branch `main` and tracks `origin/main`.
- Docker is installed and `bober` can access the Docker socket.
- PostgreSQL and Qdrant run through Docker Compose.
- PostgreSQL is reachable at `127.0.0.1:5432`.
- Qdrant is reachable at `127.0.0.1:6333`.
- LM Studio is reachable from WSL at `http://127.0.0.1:1234/v1`.
- Latest test run: `95 passed`.
- Latest live analysis smoke: `detect_missing_items` produced 2 source-cited `attachment` candidates and review report inclusion.
- Latest export smoke: missing item candidates are included in JSON/HTML review report exports with tracked export items.

## Security Baseline

Implement code with secure-by-default practices:

- parameterized SQL / ORM, no string-built SQL from user input,
- no raw rendering of user/document/LLM content as HTML,
- no user-controlled template execution,
- avoid shell calls; if unavoidable, use argument lists and no shell,
- constrain all file operations to the configured data root,
- treat LLM output as untrusted and schema/source-validate it,
- do not log secrets or full environment dumps.
