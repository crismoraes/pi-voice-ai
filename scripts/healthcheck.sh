#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
app_host="127.0.0.1"
app_port="8000"
max_attempts="${HEALTHCHECK_ATTEMPTS:-20}"
retry_delay="${HEALTHCHECK_RETRY_DELAY:-1}"

if [[ -f "$project_dir/.env" ]]; then
    configured_port="$(sed -n 's/^APP_PORT=//p' "$project_dir/.env" | tail -n 1)"
    if [[ "$configured_port" =~ ^[0-9]+$ ]]; then
        app_port="$configured_port"
    fi
fi

last_result="connection failed"
for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    if response="$(curl --fail --silent --show-error --max-time 5 "http://$app_host:$app_port/health" 2>&1)"; then
        if [[ "$response" == '{"status":"ok"}' ]]; then
            printf 'Health check passed on attempt %d: %s\n' "$attempt" "$response"
            exit 0
        fi
        last_result="unexpected response: $response"
    else
        last_result="$response"
    fi

    if ((attempt < max_attempts)); then
        sleep "$retry_delay"
    fi
done

printf 'Health check failed after %d attempts: %s\n' "$max_attempts" "$last_result" >&2
exit 1
