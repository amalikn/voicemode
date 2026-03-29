#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DATA_ROOT="${VOICEMODE_OLLAMA_VOICE_DATA_DIR:-/Volumes/Data/_ai/_mcp/mcp-data/voicemode/ollama-voice}"
RUN_DIR="${VOICEMODE_OLLAMA_VOICE_RUN_DIR:-${DATA_ROOT}/run}"
LOG_DIR="${VOICEMODE_OLLAMA_VOICE_LOG_DIR:-${DATA_ROOT}/logs}"
HOST="${VOICEMODE_OLLAMA_VOICE_HOST:-127.0.0.1}"
PORT="${VOICEMODE_OLLAMA_VOICE_PORT:-11435}"
VOICE_API_URL="http://${HOST}:${PORT}"
PID_FILE="${RUN_DIR}/ollama-voice.pid"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.voicemode.ollama-voice.plist"
LABEL="gui/$(id -u)/com.voicemode.ollama-voice"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"
STOP_LOG="${LOG_DIR}/stop.log"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "${STOP_LOG}" >&2
}

runtime_running() {
    curl -fsS "${VOICE_API_URL}/api/version" >/dev/null 2>&1
}

wait_for_stop() {
    local seconds="${1:-15}"
    local i
    for ((i=0; i<seconds; i++)); do
        if ! runtime_running; then
            return 0
        fi
        sleep 1
    done
    return 1
}

if launchctl print "${LABEL}" >/dev/null 2>&1; then
    log "Stopping launchd service ${LABEL}"
    launchctl bootout "${LABEL}" >/dev/null 2>&1 || true
fi

if [[ -f "${PID_FILE}" ]]; then
    pid="$(cat "${PID_FILE}")"
    if kill -0 "${pid}" >/dev/null 2>&1; then
        log "Stopping dedicated voice runtime PID ${pid}"
        kill "${pid}" >/dev/null 2>&1 || true
        if ! wait_for_stop 10; then
            log "Process ${pid} did not stop after SIGTERM; sending SIGKILL"
            kill -9 "${pid}" >/dev/null 2>&1 || true
        fi
    fi
    rm -f "${PID_FILE}"
fi

if runtime_running; then
    log "Runtime still reachable after PID cleanup; attempting unload via API"
    curl -fsS "${VOICE_API_URL}/api/generate" \
        -H "Content-Type: application/json" \
        -d '{"model":"phi4-mini-voice","keep_alive":0,"stream":false}' >/dev/null 2>&1 || true
fi

if runtime_running; then
    log "Dedicated voice runtime still reachable at ${VOICE_API_URL}"
    exit 1
fi

log "Dedicated voice runtime is stopped"

if [[ -f "${PLIST_DEST}" ]]; then
    log "LaunchAgent template remains installed at ${PLIST_DEST}"
fi
