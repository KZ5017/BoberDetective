#!/usr/bin/env bash
set -euo pipefail

repo_root="/home/bober/projects/Codex_BoberDetective"

for pid_file in /tmp/boberdetective-backend.pid /tmp/boberdetective-frontend.pid; do
  if [[ -f "$pid_file" ]]; then
    pid="$(<"$pid_file")"
    kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    rm -f "$pid_file"
  fi
done

pkill -f '/home/bober/projects/[C]odex_BoberDetective/.venv/bin/python.*uvicorn app.main:app' 2>/dev/null || true
pkill -f '/home/bober/projects/[C]odex_BoberDetective/frontend/node_modules/.bin/vite' 2>/dev/null || true

cd "$repo_root"
docker compose down

echo "A BoberDetective leallt."