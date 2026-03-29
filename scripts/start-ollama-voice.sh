#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DATA_ROOT="${VOICEMODE_OLLAMA_VOICE_DATA_DIR:-/Volumes/Data/_ai/_mcp/mcp-data/voicemode/ollama-voice}"
LOG_DIR="${VOICEMODE_OLLAMA_VOICE_LOG_DIR:-${DATA_ROOT}/logs}"
RUN_DIR="${VOICEMODE_OLLAMA_VOICE_RUN_DIR:-${DATA_ROOT}/run}"
MODELS_DIR="${VOICEMODE_OLLAMA_VOICE_MODELS_DIR:-${DATA_ROOT}/models}"
HOST="${VOICEMODE_OLLAMA_VOICE_HOST:-127.0.0.1}"
PORT="${VOICEMODE_OLLAMA_VOICE_PORT:-11435}"
ALIAS_MODEL="${VOICEMODE_OLLAMA_VOICE_ALIAS:-phi4-mini-voice}"
OLLAMA_BINARY="${OLLAMA_BINARY:-/Applications/Ollama.app/Contents/Resources/ollama}"
DEFAULT_MODELS_DIR="${OLLAMA_DEFAULT_MODELS_DIR:-${HOME}/.ollama/models}"
DEFAULT_API_URL="${VOICEMODE_OLLAMA_DEFAULT_BASE_URL:-http://127.0.0.1:11434}"
VOICE_API_URL="http://${HOST}:${PORT}"
MODELFILE_PATH="${VOICEMODE_OLLAMA_VOICE_MODELFILE:-${REPO_ROOT}/config/Modelfile.phi4-mini-voice}"
PLIST_TEMPLATE="${REPO_ROOT}/config/com.voicemode.ollama-voice.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.voicemode.ollama-voice.plist"
PID_FILE="${RUN_DIR}/ollama-voice.pid"
STARTUP_LOG="${LOG_DIR}/startup.log"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"

log() {
    local msg="$1"
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${msg}" | tee -a "${STARTUP_LOG}" >&2
}

die() {
    log "ERROR: $1"
    exit 1
}

usage() {
    cat <<EOF
Usage: $(basename "$0") [--serve|--install-launchagent|--start-launchagent|--status]

Default mode starts a dedicated background Ollama voice runtime on ${VOICE_API_URL}.

Options:
  --serve                Run the dedicated Ollama runtime in the foreground.
  --install-launchagent  Render the launchd template into ~/Library/LaunchAgents.
  --start-launchagent    Install (if needed) and bootstrap/kickstart the launch agent.
  --status               Print runtime status and detected model state.
EOF
}

require_file() {
    local path="$1"
    [[ -f "${path}" ]] || die "Required file not found: ${path}"
}

require_binary() {
    local path="$1"
    [[ -x "${path}" ]] || die "Required executable not found: ${path}"
}

wait_for_api() {
    local url="$1"
    local seconds="${2:-30}"
    local i
    for ((i=0; i<seconds; i++)); do
        if curl -fsS "${url}/api/version" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

runtime_running() {
    curl -fsS "${VOICE_API_URL}/api/version" >/dev/null 2>&1
}

pid_is_live() {
    if [[ ! -f "${PID_FILE}" ]]; then
        return 1
    fi
    local pid
    pid="$(cat "${PID_FILE}")"
    kill -0 "${pid}" >/dev/null 2>&1
}

cleanup_stale_pidfile() {
    if [[ -f "${PID_FILE}" ]] && ! pid_is_live; then
        rm -f "${PID_FILE}"
    fi
}

show_status() {
    cleanup_stale_pidfile
    local running="stopped"
    if runtime_running; then
        running="running"
    fi
    echo "Voice runtime: ${running}"
    echo "Voice URL: ${VOICE_API_URL}"
    echo "Voice data root: ${DATA_ROOT}"
    echo "Voice models dir: ${MODELS_DIR}"
    if [[ -f "${PID_FILE}" ]]; then
        echo "PID file: ${PID_FILE} ($(cat "${PID_FILE}"))"
    else
        echo "PID file: ${PID_FILE} (missing)"
    fi
    if runtime_running; then
        echo "Models:"
        curl -fsS "${VOICE_API_URL}/api/tags" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for item in data.get("models", []):
    name = item.get("name", "<unknown>")
    detail = item.get("details", {})
    quant = detail.get("quantization_level", "?")
    size = detail.get("parameter_size", "?")
    print(f"  - {name} ({size}, {quant})")
'
    fi
}

detect_base_model() {
    python3 - <<'PY' "${DEFAULT_API_URL}" "${DEFAULT_MODELS_DIR}"
import json
import pathlib
import sys
import urllib.error
import urllib.request

default_api = sys.argv[1].rstrip("/")
default_models = pathlib.Path(sys.argv[2])

manifest_dir = default_models / "manifests" / "registry.ollama.ai" / "library" / "phi4-mini"
preferred_tag = "3.8b-q4_K_M"

if (manifest_dir / preferred_tag).exists():
    print(f"phi4-mini:{preferred_tag}")
    raise SystemExit(0)

def pick_from_api():
    with urllib.request.urlopen(f"{default_api}/api/tags", timeout=3.0) as response:
        payload = json.load(response)
    candidates = []
    for entry in payload.get("models", []):
        name = entry.get("name", "")
        if not name.startswith("phi4-mini"):
            continue
        details = entry.get("details") or {}
        quant = (details.get("quantization_level") or "").upper()
        score = 0
        if quant == "Q4_K_M":
            score = 3
        elif quant.startswith("Q4"):
            score = 2
        elif quant:
            score = 1
        candidates.append((score, name))
    if candidates:
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][1]
    raise RuntimeError("No phi4-mini candidates found via API")

try:
    print(pick_from_api())
    raise SystemExit(0)
except Exception:
    pass

if (manifest_dir / "latest").exists():
    print("phi4-mini:latest")
    raise SystemExit(0)

tags = sorted(p.name for p in manifest_dir.iterdir() if p.is_file()) if manifest_dir.exists() else []
if tags:
    print(f"phi4-mini:{tags[0]}")
    raise SystemExit(0)

raise SystemExit(1)
PY
}

copy_base_manifest() {
    local base_model="$1"
    local base_tag="${base_model#*:}"
    local src_manifest="${DEFAULT_MODELS_DIR}/manifests/registry.ollama.ai/library/phi4-mini/${base_tag}"
    local dst_manifest_dir="${MODELS_DIR}/manifests/registry.ollama.ai/library/phi4-mini"
    require_file "${src_manifest}"
    mkdir -p "${dst_manifest_dir}"
    cp "${src_manifest}" "${dst_manifest_dir}/${base_tag}"
}

materialize_base_blobs() {
    local base_model="$1"
    local base_tag="${base_model#*:}"
    local src_manifest="${DEFAULT_MODELS_DIR}/manifests/registry.ollama.ai/library/phi4-mini/${base_tag}"
    mkdir -p "${MODELS_DIR}/blobs"
    python3 - <<'PY' "${src_manifest}" "${DEFAULT_MODELS_DIR}" "${MODELS_DIR}"
import json
import pathlib
import shutil
import sys

manifest_path = pathlib.Path(sys.argv[1])
default_models = pathlib.Path(sys.argv[2])
voice_models = pathlib.Path(sys.argv[3])

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
digests = [manifest["config"]["digest"]]
digests.extend(layer["digest"] for layer in manifest.get("layers", []))

for digest in digests:
    blob_name = digest.replace(":", "-")
    src = default_models / "blobs" / blob_name
    dst = voice_models / "blobs" / blob_name
    if dst.exists():
        continue
    if not src.exists():
        raise SystemExit(f"Missing source blob: {src}")
    try:
        dst.hardlink_to(src)
    except OSError:
        shutil.copy2(src, dst)
PY
}

prepare_models_dir() {
    local base_model="$1"
    mkdir -p "${MODELS_DIR}"
    if [[ -L "${MODELS_DIR}/blobs" ]]; then
        log "Replacing legacy shared blobs symlink with a private voice blobs directory"
        rm -f "${MODELS_DIR}/blobs"
    fi
    mkdir -p "${MODELS_DIR}/blobs"
    copy_base_manifest "${base_model}"
    materialize_base_blobs "${base_model}"
}

ensure_alias_model() {
    local base_model="$1"
    python3 - <<'PY' "${MODELFILE_PATH}" "${VOICE_API_URL}" "${ALIAS_MODEL}" "${base_model}"
import json
import pathlib
import sys
import urllib.error
import urllib.request

modelfile_path = pathlib.Path(sys.argv[1])
base_url = sys.argv[2].rstrip("/")
alias_model = sys.argv[3]
base_model = sys.argv[4]

raw = modelfile_path.read_text(encoding="utf-8")
lines = raw.splitlines()
parameters = {}
system_lines = []
template = None
from_model = None
in_system = False

for line in lines:
    stripped = line.strip()
    if not stripped:
        if in_system:
            system_lines.append("")
        continue
    if in_system:
        if stripped == '"""':
            in_system = False
        else:
            system_lines.append(line)
        continue
    if stripped.startswith("FROM "):
        from_model = stripped[5:].strip()
        continue
    if stripped.startswith("PARAMETER "):
        _, _, rest = stripped.partition("PARAMETER ")
        key, _, value = rest.partition(" ")
        if not key or not value:
            raise SystemExit(f"Invalid PARAMETER line: {line}")
        lowered = value.strip().lower()
        if lowered in {"true", "false"}:
            parsed = lowered == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value.strip().strip('"')
        parameters[key] = parsed
        continue
    if stripped.startswith('SYSTEM """'):
        if stripped != 'SYSTEM """':
            tail = stripped[len('SYSTEM """'):]
            if tail.endswith('"""'):
                system_lines.append(tail[:-3])
            else:
                system_lines.append(tail)
                in_system = True
        else:
            in_system = True
        continue
    if stripped.startswith("TEMPLATE "):
        template = stripped[len("TEMPLATE "):].strip().strip('"')

payload = {
    "model": alias_model,
    "from": base_model,
    "system": "\n".join(system_lines).strip(),
    "parameters": parameters,
    "stream": False,
}
if template:
    payload["template"] = template

def request(method, path, body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20.0) as response:
        return json.load(response)

tags = request("GET", "/api/tags")
models = {item.get("name") for item in tags.get("models", []) if isinstance(item, dict)}
if alias_model in models or f"{alias_model}:latest" in models:
    print(f"alias-ready:{alias_model}")
    raise SystemExit(0)

result = request("POST", "/api/create", payload)
status = result.get("status", "")
if status != "success":
    raise SystemExit(f"Alias creation returned unexpected status: {result}")
print(f"alias-created:{alias_model}")
PY
}

verify_alias_model() {
    python3 - <<'PY' "${VOICE_API_URL}" "${ALIAS_MODEL}"
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
alias_model = sys.argv[2]

req = urllib.request.Request(
    f"{base_url}/api/show",
    data=json.dumps({"model": alias_model}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=10.0) as response:
    payload = json.load(response)
parameters = payload.get("parameters", "")
system = payload.get("system", "")
if "num_ctx" not in parameters or "4096" not in parameters:
    raise SystemExit("Alias exists but does not report num_ctx 4096")
if "temperature" not in parameters or "0.2" not in parameters:
    raise SystemExit("Alias exists but does not report temperature 0.2")
if "current time" not in system or "filesystem" not in system:
    raise SystemExit("Alias exists but guardrail system prompt was not returned")
print("alias-verified")
PY
}

render_launchagent() {
    require_file "${PLIST_TEMPLATE}"
    mkdir -p "$(dirname "${PLIST_DEST}")" "${LOG_DIR}"
    python3 - <<'PY' "${PLIST_TEMPLATE}" "${PLIST_DEST}" "${REPO_ROOT}" "${DATA_ROOT}" "${HOME}"
import pathlib
import sys

template_path = pathlib.Path(sys.argv[1])
dest_path = pathlib.Path(sys.argv[2])
repo_root = sys.argv[3]
data_root = sys.argv[4]
home = sys.argv[5]

text = template_path.read_text(encoding="utf-8")
text = text.replace("__REPO_ROOT__", repo_root)
text = text.replace("__DATA_ROOT__", data_root)
text = text.replace("__HOME__", home)
dest_path.write_text(text, encoding="utf-8")
print(dest_path)
PY
    plutil -lint "${PLIST_DEST}" >/dev/null
    log "Rendered launch agent to ${PLIST_DEST}"
}

start_background_runtime() {
    local base_model="$1"
    prepare_models_dir "${base_model}"
    cleanup_stale_pidfile

    if runtime_running; then
        log "Dedicated voice runtime already reachable at ${VOICE_API_URL}"
        ensure_alias_model "${base_model}"
        verify_alias_model
        return 0
    fi

    if [[ -f "${PID_FILE}" ]]; then
        local stale_pid
        stale_pid="$(cat "${PID_FILE}")"
        if kill -0 "${stale_pid}" >/dev/null 2>&1; then
            log "Found existing PID ${stale_pid}, waiting for API"
            if wait_for_api "${VOICE_API_URL}" 20; then
                ensure_alias_model "${base_model}"
                verify_alias_model
                return 0
            fi
        fi
        rm -f "${PID_FILE}"
    fi

    log "Starting dedicated voice runtime on ${VOICE_API_URL}"
    nohup env \
        OLLAMA_HOST="${HOST}:${PORT}" \
        OLLAMA_MODELS="${MODELS_DIR}" \
        OLLAMA_FLASH_ATTENTION=1 \
        OLLAMA_KV_CACHE_TYPE=q8_0 \
        OLLAMA_NOPRUNE=1 \
        "${OLLAMA_BINARY}" serve \
        >>"${LOG_DIR}/ollama-voice.out.log" \
        2>>"${LOG_DIR}/ollama-voice.err.log" \
        </dev/null &
    local pid=$!
    echo "${pid}" > "${PID_FILE}"
    log "Spawned dedicated voice runtime with PID ${pid}"

    if ! wait_for_api "${VOICE_API_URL}" 30; then
        rm -f "${PID_FILE}"
        die "Dedicated runtime did not become ready on ${VOICE_API_URL}"
    fi

    ensure_alias_model "${base_model}"
    verify_alias_model
    log "Dedicated voice runtime is ready at ${VOICE_API_URL} with alias ${ALIAS_MODEL}"
}

serve_foreground() {
    local base_model="$1"
    prepare_models_dir "${base_model}"
    export OLLAMA_HOST="${HOST}:${PORT}"
    export OLLAMA_MODELS="${MODELS_DIR}"
    export OLLAMA_FLASH_ATTENTION=1
    export OLLAMA_KV_CACHE_TYPE=q8_0
    export OLLAMA_NOPRUNE=1
    log "Running dedicated voice runtime in foreground on ${VOICE_API_URL}"
    exec "${OLLAMA_BINARY}" serve
}

install_and_start_launchagent() {
    render_launchagent
    if launchctl print "gui/$(id -u)/com.voicemode.ollama-voice" >/dev/null 2>&1; then
        launchctl kickstart -k "gui/$(id -u)/com.voicemode.ollama-voice"
    else
        launchctl bootstrap "gui/$(id -u)" "${PLIST_DEST}"
    fi
    if ! wait_for_api "${VOICE_API_URL}" 30; then
        die "LaunchAgent started but the dedicated runtime is not reachable at ${VOICE_API_URL}"
    fi
    local base_model
    base_model="$(detect_base_model)" || die "Unable to detect a local phi4-mini base model"
    ensure_alias_model "${base_model}"
    verify_alias_model
    log "LaunchAgent runtime is ready at ${VOICE_API_URL}"
}

main() {
    require_file "${MODELFILE_PATH}"
    require_binary "${OLLAMA_BINARY}"

    local mode="${1:-}"
    case "${mode}" in
        -h|--help)
            usage
            ;;
        --status)
            show_status
            ;;
        --install-launchagent)
            render_launchagent
            ;;
        --start-launchagent)
            install_and_start_launchagent
            ;;
        --serve)
            local base_model
            base_model="$(detect_base_model)" || die "Unable to detect a local phi4-mini base model"
            serve_foreground "${base_model}"
            ;;
        "")
            local base_model
            base_model="$(detect_base_model)" || die "Unable to detect a local phi4-mini base model"
            log "Selected base model ${base_model}"
            start_background_runtime "${base_model}"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
