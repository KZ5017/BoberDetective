#!/usr/bin/env bash
set -euo pipefail

repo_root="/home/bober/projects/Codex_BoberDetective"
backend_pid_file="/tmp/boberdetective-backend.pid"
frontend_pid_file="/tmp/boberdetective-frontend.pid"

cd "$repo_root"
docker compose up -d

if [[ -f "$backend_pid_file" ]] && kill -0 "$(<"$backend_pid_file")" 2>/dev/null; then
  echo "A BoberDetective backend mar fut."
else
  rm -f "$backend_pid_file"
  setsid -f sh -c 'echo $$ > /tmp/boberdetective-backend.pid; exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/boberdetective-backend.log 2>&1 < /dev/null'
fi

if [[ -f "$frontend_pid_file" ]] && kill -0 "$(<"$frontend_pid_file")" 2>/dev/null; then
  echo "A BoberDetective frontend mar fut."
else
  rm -f "$frontend_pid_file"
  setsid -f sh -c 'echo $$ > /tmp/boberdetective-frontend.pid; exec npm --prefix frontend run dev -- --host 0.0.0.0 --port 5174 --strictPort > /tmp/boberdetective-frontend.log 2>&1 < /dev/null'
fi

for _ in $(seq 1 20); do
  curl -fsS http://127.0.0.1:8001/api/v1/system/health >/dev/null && break
  sleep 1
done
curl -fsS http://127.0.0.1:8001/api/v1/system/health >/dev/null

for _ in $(seq 1 20); do
  curl -fsSI http://127.0.0.1:5174 >/dev/null && break
  sleep 1
done
curl -fsSI http://127.0.0.1:5174 >/dev/null

echo "BoberDetective elindult: http://localhost:5174"