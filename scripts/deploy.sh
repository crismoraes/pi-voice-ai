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
sudo systemctl restart pi-voice-ai.service
"$project_dir/scripts/healthcheck.sh"
sudo systemctl --no-pager --full status pi-voice-ai.service
sudo journalctl -u pi-voice-ai.service --since '-5 minutes' --priority=err --no-pager
