#!/usr/bin/env bash
set -Eeuo pipefail
sudo systemctl stop pi-voice-ai.service
sudo systemctl --no-pager --full status pi-voice-ai.service || true
