#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run-voice-model.sh phi "prompt"
  ./scripts/run-voice-model.sh gemma "prompt"
  ./scripts/run-voice-model.sh phi
EOF
}

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama is not installed or not on PATH" >&2
  exit 1
fi

target="${1:-}"
prompt="${2-}"

case "${target}" in
  phi)
    model="phi4-mini-voice"
    ;;
  gemma)
    model="gemma-3-4b-voice"
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac

if ! ollama show "${model}" >/dev/null 2>&1; then
  echo "Model alias '${model}' is not available. Create it first with ollama create." >&2
  exit 1
fi

# The alias Modelfile pins num_ctx=4096, so plain `ollama run` uses that context window.
if [[ -n "${prompt}" ]]; then
  exec ollama run "${model}" "${prompt}"
fi

exec ollama run "${model}"
