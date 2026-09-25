#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
app_host="127.0.0.1"
app_port="8000"

if [[ -f "$project_dir/.env" ]]; then
    configured_port="$(sed -n 's/^APP_PORT=//p' "$project_dir/.env" | tail -n 1)"
    if [[ "$configured_port" =~ ^[0-9]+$ ]]; then
        app_port="$configured_port"
    fi
fi

response="$(curl --fail --silent --show-error --max-time 5 "http://$app_host:$app_port/health")"
if [[ "$response" != '{"status":"ok"}' ]]; then
    printf 'Unexpected health response: %s\n' "$response" >&2
    exit 1
fi
printf 'Health check passed: %s\n' "$response"
