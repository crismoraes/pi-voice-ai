#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ -n "$(git status --porcelain)" ]]; then
    printf 'Deployment stopped: the Raspberry Pi working tree is not clean.\n' >&2
    git status --short
    exit 1
fi

git fetch origin
git pull --ff-only
"$project_dir/scripts/bootstrap_pi.sh"
"$project_dir/.venv/bin/python" -m compileall -q "$project_dir/app"
"$project_dir/.venv/bin/python" -m pytest
"$project_dir/scripts/install_service.sh"
sudo systemctl restart pi-voice-ai-llm.service
for attempt in {1..60}; do
    if curl --fail --silent --show-error http://127.0.0.1:8081/health >/dev/null; then
        break
    fi
    if [[ "$attempt" == 60 ]]; then
        printf 'Local LLM did not become ready within 120 seconds.\n' >&2
        exit 1
    fi
    sleep 2
done
sudo systemctl restart pi-voice-ai.service
"$project_dir/scripts/healthcheck.sh"
sudo systemctl --no-pager --full status pi-voice-ai.service
sudo systemctl --no-pager --full status pi-voice-ai-llm.service
sudo journalctl -u pi-voice-ai.service --since '-5 minutes' --priority=err --no-pager
sudo journalctl -u pi-voice-ai-llm.service --since '-5 minutes' --priority=err --no-pager
