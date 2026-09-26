#!/usr/bin/env bash
set -u

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

printf '== PiVoice AI service ==\n'
systemctl show pi-voice-ai.service \
    -p ActiveState -p SubState -p UnitFileState -p NRestarts -p ExecMainStatus \
    --no-pager || true

printf '\n== Application endpoints ==\n'
"$project_dir/scripts/healthcheck.sh" || true

printf '\n== ALSA devices and processes ==\n'
arecord -l 2>&1 || true
aplay -l 2>&1 || true
pgrep -a arecord || printf 'arecord is not running\n'
pgrep -a aplay || printf 'aplay is not running\n'

printf '\n== Raspberry Pi resources ==\n'
free -h || true
df -h / || true
command -v vcgencmd >/dev/null 2>&1 && vcgencmd measure_temp || true
command -v vcgencmd >/dev/null 2>&1 && vcgencmd get_throttled || true

printf '\n== Recent warnings and errors ==\n'
journalctl -u pi-voice-ai.service --since '-10 minutes' \
    --priority=warning --no-pager || true

printf '\nDiagnostic complete. This report does not read .env or credentials.\n'
