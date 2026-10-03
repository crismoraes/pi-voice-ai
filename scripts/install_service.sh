#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
service_source="$project_dir/systemd/pi-voice-ai.service"
service_target="/etc/systemd/system/pi-voice-ai.service"
llm_service_source="$project_dir/systemd/pi-voice-ai-llm.service"
llm_service_target="/etc/systemd/system/pi-voice-ai-llm.service"
app_user="${SUDO_USER:-$USER}"
rendered_service="$(mktemp)"
rendered_llm_service="$(mktemp)"
trap 'rm -f "$rendered_service" "$rendered_llm_service"' EXIT

if [[ "$app_user" == "root" ]]; then
    printf 'Run with sudo from the non-root account that should own the service.\n' >&2
    exit 1
fi

escaped_project_dir=${project_dir//&/\\&}
escaped_app_user=${app_user//&/\\&}
sed \
    -e "s&__APP_DIR__&$escaped_project_dir&g" \
    -e "s&__APP_USER__&$escaped_app_user&g" \
    "$service_source" > "$rendered_service"
sed \
    -e "s&__APP_DIR__&$escaped_project_dir&g" \
    -e "s&__APP_USER__&$escaped_app_user&g" \
    "$llm_service_source" > "$rendered_llm_service"

sudo install -o root -g root -m 0644 "$rendered_service" "$service_target"
sudo install -o root -g root -m 0644 "$rendered_llm_service" "$llm_service_target"
sudo systemctl daemon-reload
sudo systemctl enable pi-voice-ai-llm.service
sudo systemctl enable pi-voice-ai.service
printf 'Installed PiVoice AI services for user %s.\n' "$app_user"
