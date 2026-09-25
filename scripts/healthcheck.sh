#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
app_host="127.0.0.1"
app_port="8000"
app_scheme="http"
tls_ca_file=""
max_attempts="${HEALTHCHECK_ATTEMPTS:-20}"
retry_delay="${HEALTHCHECK_RETRY_DELAY:-1}"

if [[ -f "$project_dir/.env" ]]; then
    configured_port="$(sed -n 's/^APP_PORT=//p' "$project_dir/.env" | tail -n 1)"
    if [[ "$configured_port" =~ ^[0-9]+$ ]]; then
        app_port="$configured_port"
    fi
    tls_cert_file="$(sed -n 's/^TLS_CERT_FILE=//p' "$project_dir/.env" | tail -n 1)"
    tls_ca_file="$(sed -n 's/^TLS_CA_FILE=//p' "$project_dir/.env" | tail -n 1)"
    if [[ -n "$tls_cert_file" ]]; then
        app_scheme="https"
        app_host="$(hostname)"
    fi
fi

curl_options=(--fail --silent --show-error --max-time 5)
if [[ "$app_scheme" == "https" && -n "$tls_ca_file" ]]; then
    curl_options+=(--cacert "$tls_ca_file")
    curl_options+=(--resolve "$app_host:$app_port:127.0.0.1")
fi

last_result="connection failed"
for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    if response="$(curl "${curl_options[@]}" "$app_scheme://$app_host:$app_port/health" 2>&1)"; then
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
