$ErrorActionPreference = "Stop"
& wsl -d Ubuntu-24.04 -u bober bash -lc 'cd /home/bober/projects/Codex_BoberDetective && ./scripts/start-services.sh'
if ($LASTEXITCODE -ne 0) {
    throw "A BoberDetective inditasa sikertelen."
}