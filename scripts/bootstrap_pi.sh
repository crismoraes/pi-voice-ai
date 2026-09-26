#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$(uname -m)" != "aarch64" ]]; then
    printf 'Expected aarch64 Raspberry Pi, found %s\n' "$(uname -m)" >&2
    exit 1
fi

missing_packages=()
command -v git >/dev/null 2>&1 || missing_packages+=(git)
command -v python3 >/dev/null 2>&1 || missing_packages+=(python3)
command -v curl >/dev/null 2>&1 || missing_packages+=(curl)
command -v bzip2 >/dev/null 2>&1 || missing_packages+=(bzip2)
if command -v python3 >/dev/null 2>&1; then
    python3 -m venv --help >/dev/null 2>&1 || missing_packages+=(python3-venv)
    python3 -m pip --version >/dev/null 2>&1 || missing_packages+=(python3-pip)
fi

if ((${#missing_packages[@]})); then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends "${missing_packages[@]}"
else
    printf 'Required system packages are already installed.\n'
fi

if [[ ! -d "$project_dir/.venv" ]]; then
    python3 -m venv "$project_dir/.venv"
fi

"$project_dir/.venv/bin/python" -m pip install --upgrade 'pip>=25,<27'
"$project_dir/.venv/bin/python" -m pip install -e "$project_dir[dev]"
"$project_dir/scripts/download_stt_model.sh"

if [[ ! -f "$project_dir/.env" ]]; then
    cp "$project_dir/.env.example" "$project_dir/.env"
    chmod 600 "$project_dir/.env"
    printf 'Created %s from .env.example; configure it locally on the Pi.\n' "$project_dir/.env"
fi

printf 'Bootstrap complete: %s\n' "$project_dir"
