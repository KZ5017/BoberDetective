# BoberDetective Frontend

Minimal React/Vite workbench for the local backend.

## Development

Start the backend from the repository root:

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Start the frontend from this directory:

```bash
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

Current workflows:

- case list/create,
- TXT import,
- document list,
- document page/chunk drill-down,
- analysis module run,
- analysis run history,
- analysis run input/output detail,
- elapsed-time feedback for long operations,
- review report filtering by object type, review status, and source validation status,
- focused review queue shortcuts,
- object detail inspection,
- source detail and review history inspection,
- review actions for report items,
- JSON/HTML export creation and download,
- export history.

## Verification

```bash
npm run build
```

Latest live frontend/API smoke also passed against the running backend and Vite dev server: case creation, TXT import, all MVP analysis modules, review queue filter, claim review, JSON export/list/download, frontend index, and `/api` proxy.
