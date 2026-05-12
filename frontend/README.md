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
- analysis module run,
- review report filtering,
- review actions for report items,
- JSON/HTML export creation and download.

## Verification

```bash
npm run build
```
