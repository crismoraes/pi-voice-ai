#!/usr/bin/env bash
set -Eeuo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sudo systemctl restart pi-voice-ai.service
"$project_dir/scripts/healthcheck.sh"
