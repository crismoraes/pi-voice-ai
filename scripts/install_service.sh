#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
service_source="$project_dir/systemd/pi-voice-ai.service"
service_target="/etc/systemd/system/pi-voice-ai.service"
app_user="${SUDO_USER:-$USER}"
rendered_service="$(mktemp)"
trap 'rm -f "$rendered_service"' EXIT

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

sudo install -o root -g root -m 0644 "$rendered_service" "$service_target"
sudo systemctl daemon-reload
sudo systemctl enable pi-voice-ai.service
printf 'Installed %s for user %s.\n' "$service_target" "$app_user"
