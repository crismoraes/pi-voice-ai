#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
models_dir="$project_dir/models"
mkdir -p "$models_dir"

install_model() {
    local model_name="$1" model_file="$2" expected_sha256="$3"
    local model_dir="$models_dir/$model_name" archive
    archive="$(mktemp --suffix=.tar.bz2)"
    trap 'rm -f "$archive"' RETURN
    if [[ -f "$model_dir/$model_file" && -f "$model_dir/tokens.txt" && -d "$model_dir/espeak-ng-data" ]]; then
        printf 'TTS model already installed: %s\n' "$model_dir"
        return
    fi
    curl --fail --location --retry 3 --output "$archive" \
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$model_name.tar.bz2"
    printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check --status
    rm -rf "$model_dir"
    tar -xjf "$archive" -C "$models_dir"
    [[ -f "$model_dir/$model_file" && -f "$model_dir/tokens.txt" && -d "$model_dir/espeak-ng-data" ]]
    printf 'TTS model installed and verified: %s\n' "$model_dir"
}

install_model "vits-piper-pt_BR-jeff-medium" "pt_BR-jeff-medium.onnx" "da4c870fc7b20600c74261b3e1dd1c816da2ce063e18c46e1f2cd86dea88f3f0"
install_model "vits-piper-en_US-lessac-medium" "en_US-lessac-medium.onnx" "9e3febfacf0abf4270172d2958bcec246032b7e88efc2720840cc80c93de334e"
install_model "vits-piper-es_ES-sharvard-medium" "es_ES-sharvard-medium.onnx" "b30a7a83df0518f0ee1c7039506648cade99f1f9b498fc49ed2ced2e2536bb5a"
