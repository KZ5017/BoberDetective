# BoberDetective Frontend

Minimal React/Vite workbench for the local backend.

## Development

Start the backend from the repository root:

```bash
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Start the frontend from this directory:

```bash
npm run dev
```

Open the frontend at:

```text
http://localhost:5173
```

The Vite dev server listens on port `5173` and proxies `/api` to `http://127.0.0.1:8000`.

For Codex/non-interactive WSL background startup, start the infrastructure first:

```bash
docker compose up -d
```

Then detach backend and frontend with `setsid -f` from the repository root:

```bash
setsid -f sh -c ".venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/boberdetective-backend.log 2>&1 < /dev/null"
setsid -f sh -c "npm --prefix frontend run dev -- --host 0.0.0.0 > /tmp/boberdetective-frontend.log 2>&1 < /dev/null"
```

Verify:

```bash
ss -ltnp | grep -E ":(8000|5173)"
curl -fsS http://127.0.0.1:8000/api/v1/system/health
curl -I http://127.0.0.1:5173
```

Current workflows:

- case list/create,
- TXT import,
- native-text PDF import through the shared document import endpoint,
- OCR action for review-required/no-page PDF documents, with document status, pages, chunks, and analysis run history refreshed after completion,
- document list,
- document page/chunk drill-down,
- analysis module run,
- source scope controls for batch-capable raw-chunk analysis modules,
- contradiction claim-pair analysis panel with optional focus, claim review scope, and selected pair metadata,
- empty-by-default analysis focus input with informational placeholders only,
- conservative contradiction candidate review notes,
- analysis run history,
- analysis run input/output detail,
- elapsed-time feedback for long operations,
- `Általános iratkérdező` with case/document/collection source scopes, case-mode selected document subsets, semantic index status, latest-query summary, temporary answer display, explicit answer saving, saved-answer list/detail/delete, and source-summary display,
- review report filtering by object type, review status, and source validation status,
- focused review queue shortcuts,
- object detail inspection,
- source detail and review history inspection,
- review actions for report items,
- JSON/HTML export creation and download,
- export history.

UI language rule:

- Keep visible frontend text Hungarian.
- Keep contradiction candidates framed as human-review candidates, not proven contradictions.
- Backend enum/internal values can remain English in API payloads, but map them to Hungarian labels before rendering.

Responsive UI note:

- Desktop/default styling, Full HD styling, and phone styling are separate layers in `src/styles.css`.
- Keep Full HD-specific changes inside the existing 1080p media query.
- Keep phone-specific layout changes inside the `max-width: 760px` mobile media query so desktop and 1080p behavior stay isolated.

## Verification

```bash
npm run build
```

Latest live frontend/API smoke also passed against the running backend and Vite dev server: case creation, TXT import, all MVP analysis modules, review queue filter, claim review, JSON export/list/download, frontend index, and `/api` proxy.
