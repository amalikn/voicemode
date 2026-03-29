#!/bin/bash

set -euo pipefail

HOST="${VOICEMODE_OLLAMA_VOICE_HOST:-127.0.0.1}"
PORT="${VOICEMODE_OLLAMA_VOICE_PORT:-11435}"
VOICE_API_URL="http://${HOST}:${PORT}"
ALIAS_MODEL="${VOICEMODE_OLLAMA_VOICE_ALIAS:-phi4-mini-voice}"

python3 - <<'PY' "${VOICE_API_URL}" "${ALIAS_MODEL}"
import json
import sys
import urllib.error
import urllib.request

base_url = sys.argv[1].rstrip("/")
alias_model = sys.argv[2]


def request(method, path, body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20.0) as response:
        return json.load(response)


def assert_true(condition, message):
    if not condition:
        raise SystemExit(message)


try:
    version = request("GET", "/api/version")
except urllib.error.URLError as exc:
    raise SystemExit(f"Voice runtime not reachable at {base_url}: {exc}") from exc

print(f"OK version {version.get('version', '?')} at {base_url}")

tags = request("GET", "/api/tags")
models = {item.get("name"): item for item in tags.get("models", []) if isinstance(item, dict)}
voice_entry = models.get(alias_model) or models.get(f"{alias_model}:latest")
assert_true(voice_entry is not None, f"Model {alias_model} is not present on the dedicated runtime")

details = voice_entry.get("details") or {}
print(
    "OK model present",
    voice_entry.get("name"),
    details.get("parameter_size", "?"),
    details.get("quantization_level", "?"),
)

show = request("POST", "/api/show", {"model": alias_model})
parameters = show.get("parameters", "")
system = show.get("system", "")
assert_true("num_ctx" in parameters and "4096" in parameters, "Model does not report num_ctx 4096")
assert_true("temperature" in parameters and "0.2" in parameters, "Model does not report temperature 0.2")
assert_true("current time" in system and "filesystem" in system and "network-backed facts" in system, "Guardrail system prompt is incomplete")
print("OK alias parameters and guardrails")

prompt = (
    "A user asked for a quick acknowledgment. Reply in under six words."
)
response = request(
    "POST",
    "/api/generate",
    {
        "model": alias_model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 4096, "temperature": 0.2},
        "keep_alive": "5m",
    },
)
text = str(response.get("response", "")).strip()
assert_true(bool(text), "Voice model returned an empty response")
assert_true(len(text.split()) <= 12, f"Voice model reply was too long: {text!r}")
print(f"OK short reply: {text}")

ps_data = request("GET", "/api/ps")
running = [item for item in ps_data.get("models", []) if isinstance(item, dict)]
assert_true(any(item.get("name") in {alias_model, f'{alias_model}:latest'} for item in running), "Voice model is not loaded according to /api/ps")
print("OK /api/ps reports loaded model(s):")
for item in running:
    name = item.get("name", "<unknown>")
    size = item.get("size", 0)
    size_vram = item.get("size_vram", 0)
    expires = item.get("expires_at", "?")
    print(f"  - {name}: size={size} size_vram={size_vram} expires_at={expires}")

print("PASS phi4-mini voice runtime checks")
PY
