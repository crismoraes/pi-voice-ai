#!/usr/bin/env bash
set -Eeuo pipefail
sudo systemctl start pi-voice-ai.service
sudo systemctl --no-pager --full status pi-voice-ai.service
