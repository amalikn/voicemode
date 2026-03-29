#!/bin/bash

set -euo pipefail

MANIFEST_ROOT="${OLLAMA_MANIFEST_ROOT:-${HOME}/.ollama/models/manifests/registry.ollama.ai/library}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
MODE="dry-run"

usage() {
    cat <<EOF
Usage: $(basename "$0") [--apply] [--manifest-root PATH] [--base-url URL]

Recover locally-manifested Ollama models by re-pulling them through the Ollama
HTTP API. Defaults to dry-run.

Options:
  --apply                 Perform the pulls. Without this flag, only print the plan.
  --manifest-root PATH    Override the manifest root to scan.
  --base-url URL          Override the Ollama API base URL.
  -h, --help              Show this help.
EOF
}

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >&2
}

require_path() {
    [[ -d "$1" ]] || {
        log "ERROR: manifest root not found: $1"
        exit 1
    }
}

collect_models() {
    python3 - <<'PY' "${MANIFEST_ROOT}"
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
skip_names = {".DS_Store", ".webui_secret_key"}
models = []

for model_dir in sorted(root.iterdir()):
    if not model_dir.is_dir():
        continue
    model = model_dir.name
    for tag_file in sorted(model_dir.iterdir()):
        if not tag_file.is_file():
            continue
        tag = tag_file.name
        if tag in skip_names:
            continue
        models.append(f"{model}:{tag}")

for model in models:
    print(model)
PY
}

api_get() {
    curl -fsS "$1"
}

api_post_json() {
    local url="$1"
    local body="$2"
    curl -fsS "${url}" \
        -H 'Content-Type: application/json' \
        -d "${body}"
}

runtime_check() {
    api_get "${OLLAMA_BASE_URL}/api/version" >/dev/null
}

pull_model() {
    local model="$1"
    log "Pulling ${model}"
    api_post_json "${OLLAMA_BASE_URL}/api/pull" "{\"model\":\"${model}\",\"stream\":false}" >/dev/null
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply)
            MODE="apply"
            shift
            ;;
        --manifest-root)
            MANIFEST_ROOT="$2"
            shift 2
            ;;
        --base-url)
            OLLAMA_BASE_URL="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log "ERROR: unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

require_path "${MANIFEST_ROOT}"

models=()
while IFS= read -r model; do
    [[ -n "${model}" ]] && models+=("${model}")
done < <(collect_models)

if [[ ${#models[@]} -eq 0 ]]; then
    log "No manifest-backed models found under ${MANIFEST_ROOT}"
    exit 0
fi

printf 'Manifest-backed models under %s:\n' "${MANIFEST_ROOT}"
printf '  %s\n' "${models[@]}"

if [[ "${MODE}" != "apply" ]]; then
    printf '\nDry run only. Re-run with --apply to pull all %d models from %s.\n' "${#models[@]}" "${OLLAMA_BASE_URL}"
    exit 0
fi

runtime_check

for model in "${models[@]}"; do
    pull_model "${model}"
done

printf '\nRecovery pull complete for %d models from %s.\n' "${#models[@]}" "${OLLAMA_BASE_URL}"
