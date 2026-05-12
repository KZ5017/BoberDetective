# Current State

## Session Handoff Baseline v1

This file is the quick-start handoff for a fresh Codex session.

Read these first:

- `AGENTS.md`
- `README.md`
- `AI_NOTES.md`
- `CHANGELOG.md`
- `CURRENT_STATE.md`

Then run:

```bash
.venv/bin/pytest -q
.venv/bin/alembic current
```

Expected current baseline:

```text
pytest: 52 passed
alembic: 0008_exports (head)
```

## What Works Now

- FastAPI backend scaffold.
- PostgreSQL and Qdrant Docker Compose development runtime.
- SQLAlchemy/psycopg database layer.
- Alembic migrations through `0008_exports`.
- Immutable TXT import with page/chunk persistence.
- Keyword search over current page/chunk text.
- Source references with quote validation.
- LM Studio provider abstraction and local model smoke checks.
- Analysis run provenance.
- Source-cited `extract_claims` and `extract_events` modules.
- Claim, event, source, review, export, and audit persistence.
- Case review report endpoint.
- JSON review report export with SHA256 and export item tracking.
- Append-only human review history for claims and exports.

## Current Tables

Current database head has:

```text
users, cases, case_users, audit_events,
documents, document_pages, document_chunks,
source_references,
analysis_runs, analysis_run_inputs, analysis_run_outputs,
claims, claim_sources,
events, event_sources,
human_reviews,
exports, export_items,
alembic_version
```

## Main API Surface

System:

- `GET /api/v1/system/health`
- `GET /api/v1/system/llm/smoke`

Cases and documents:

- `GET /api/v1/cases`
- `POST /api/v1/cases`
- `GET /api/v1/cases/{case_id}/documents`
- `POST /api/v1/cases/{case_id}/documents`
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
- `POST /api/v1/cases/{case_id}/analysis/modules/extract_claims`
- `POST /api/v1/cases/{case_id}/analysis/modules/extract_events`

Reviewable objects:

- `GET /api/v1/cases/{case_id}/claims`
- `GET /api/v1/cases/{case_id}/claims/{claim_id}`
- `POST /api/v1/cases/{case_id}/claims/{claim_id}/reviews`
- `GET /api/v1/cases/{case_id}/events`
- `GET /api/v1/cases/{case_id}/events/{event_id}`
- `GET /api/v1/cases/{case_id}/review-report`

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
3. Run `extract_claims`.
4. Run `extract_events`.
5. Fetch `/review-report`.
6. Create a JSON review report export.
7. Download the export.
8. Add an export review.

The latest live smoke completed this path successfully.

## Next Logical Steps

Recommended order:

1. Create and push the first baseline Git commit.
2. Add HTML export format for review reports.
3. Add event review workflow or unify review helpers across claim/export/event.
4. Add `extract_entities`.
5. Start a minimal frontend only after the backend review/export loop is stable.

## Important Local Notes

- WSL sometimes fails parallel file reads with transient service errors. Single WSL commands are more reliable.
- LM Studio native `/api/v1/chat` should use `max_output_tokens`, not `maxTokens`.
- Send `reasoning: "off"` only for Qwen-style reasoning models.
- Keep generated data under the configured data root, not inside the Git repository.
