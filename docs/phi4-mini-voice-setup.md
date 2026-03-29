# Dedicated `phi4-mini-voice` Ollama Path

This guide creates a dedicated low-latency Ollama path for the local
voice-shell model used by VoiceMode.

It is intentionally separate from the default Ollama instance so that voice
optimizations do not silently change unrelated coding, reasoning, or general
chat usage.

## What This Adds

- a dedicated model alias: `phi4-mini-voice`
- a dedicated runtime host and port: `http://127.0.0.1:11435`
- a dedicated model store rooted at:
  `/Volumes/Data/_ai/_mcp/mcp-data/voicemode/ollama-voice/models`
- a checked-in Modelfile source of truth:
  `config/Modelfile.phi4-mini-voice`
- start, stop, and validation scripts
- an optional macOS LaunchAgent template for auto-start

## Global Versus Dedicated Settings

### Dedicated to the voice runtime only

These settings are applied only by the dedicated voice runtime started through
the new script or LaunchAgent:

- `OLLAMA_HOST=127.0.0.1:11435`
- `OLLAMA_MODELS=/Volumes/Data/_ai/_mcp/mcp-data/voicemode/ollama-voice/models`
- `OLLAMA_FLASH_ATTENTION=1`
- `OLLAMA_KV_CACHE_TYPE=q8_0`
- `OLLAMA_NOPRUNE=1`

### Model-specific only

These settings live in `config/Modelfile.phi4-mini-voice` and apply only to
the `phi4-mini-voice` alias:

- `PARAMETER num_ctx 4096`
- `PARAMETER temperature 0.2`
- `PARAMETER num_predict 96`
- the short, cautious voice-shell system prompt

### Unchanged global/default Ollama path

The default Ollama instance on `127.0.0.1:11434` is not reconfigured by these
artifacts.

## Base Model Selection

The startup script prefers:

1. `phi4-mini:3.8b-q4_K_M`
2. otherwise another installed `phi4-mini` Q4 variant reported by `/api/tags`
3. otherwise `phi4-mini:latest` if that is the only local manifest available

On the current host, the detected base model is:

- `phi4-mini:latest`
- quantization reported by the default runtime: `Q4_K_M`

## How Reuse Works

The dedicated runtime uses its own `OLLAMA_MODELS` directory and keeps its own
blob directory.

To avoid redownloading `phi4-mini`, the startup script copies the selected base
manifest into the voice store and then reuses only the required blob files for
that model by creating hard links when possible, with a file-copy fallback if
hard links are unavailable.

This is intentionally not a full-directory symlink. Ollama can prune blobs that
are not referenced by the active model store, so sharing one `blobs` directory
between the default runtime and the dedicated voice runtime is unsafe.

## Files Added

- `config/Modelfile.phi4-mini-voice`
- `config/com.voicemode.ollama-voice.plist`
- `scripts/start-ollama-voice.sh`
- `scripts/stop-ollama-voice.sh`
- `scripts/test-phi4-voice.sh`

## Start The Dedicated Runtime

### Direct background start

```bash
cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode
./scripts/start-ollama-voice.sh
```

What it does:

- detects a local `phi4-mini` base model
- creates the dedicated models path
- reuses only the required `phi4-mini` blobs by hard link or file copy
- starts a dedicated Ollama server on `127.0.0.1:11435`
- creates `phi4-mini-voice` from `config/Modelfile.phi4-mini-voice` if missing
- verifies the alias reports the expected parameters and guardrails

### Optional launchd install

Render the checked-in template into `~/Library/LaunchAgents`:

```bash
cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode
./scripts/start-ollama-voice.sh --install-launchagent
```

Start the LaunchAgent:

```bash
cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode
./scripts/start-ollama-voice.sh --start-launchagent
```

The rendered label is:

- `com.voicemode.ollama-voice`

## Client Targeting

Point voice clients at the dedicated runtime instead of the default Ollama
instance:

```bash
export VOICEMODE_OLLAMA_BASE_URL=http://127.0.0.1:11435
export VOICEMODE_OLLAMA_MODEL=phi4-mini-voice
```

## Validation

### Full validation script

```bash
cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode
./scripts/test-phi4-voice.sh
```

This checks:

- the dedicated runtime is reachable
- `phi4-mini-voice` exists
- `/api/show` reports `num_ctx 4096`
- `/api/show` reports `temperature 0.2`
- the guardrail system prompt includes no-fabrication rules for time/date/system/filesystem/network facts
- the model returns a short reply
- `/api/ps` shows the model loaded in memory

### Manual spot checks

List models on the dedicated runtime:

```bash
curl -sS http://127.0.0.1:11435/api/tags | jq .
```

Show the alias configuration:

```bash
curl -sS http://127.0.0.1:11435/api/show \
  -H 'Content-Type: application/json' \
  -d '{"model":"phi4-mini-voice"}' | jq .
```

Ask for a short reply:

```bash
curl -sS http://127.0.0.1:11435/api/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"phi4-mini-voice",
    "prompt":"Give a brief acknowledgment in under six words.",
    "stream":false,
    "options":{"num_ctx":4096,"temperature":0.2}
  }' | jq -r .response
```

Inspect loaded models:

```bash
curl -sS http://127.0.0.1:11435/api/ps | jq .
```

## Expected `/api/ps` Patterns

After a short request, expect:

- `phi4-mini-voice` to appear in `models`
- `size` to be around the 3.8B Q4 model footprint
- `size_vram` to be non-zero when the model is resident in Apple GPU memory
- `expires_at` to be present while the model remains warm

If `/api/ps` is empty immediately after a request, the model was likely unloaded
or the request failed before load completed.

## Stop And Roll Back

### Stop the dedicated runtime

```bash
cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode
./scripts/stop-ollama-voice.sh
```

### Roll back the dedicated voice path

1. Stop the dedicated runtime:

```bash
./scripts/stop-ollama-voice.sh
```

2. Remove the LaunchAgent if you installed it:

```bash
launchctl bootout gui/$(id -u)/com.voicemode.ollama-voice 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.voicemode.ollama-voice.plist
```

3. Remove the dedicated voice data directory:

```bash
rm -rf /Volumes/Data/_ai/_mcp/mcp-data/voicemode/ollama-voice
```

No rollback step modifies or removes the default Ollama model store.

## Incident Recovery

If the default Ollama runtime has fewer visible models than expected but the
manifest files are still present under `~/.ollama/models/manifests`, use the
recovery script to rebuild availability by re-pulling those models through the
default Ollama API.

Dry-run the recovery plan:

```bash
cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode
./scripts/recover-ollama-models.sh
```

Perform the recovery pulls:

```bash
cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode
./scripts/recover-ollama-models.sh --apply
```

The script:

- scans `~/.ollama/models/manifests/registry.ollama.ai/library`
- converts manifest paths into model names such as `qwen2.5-coder:14b`
- uses `POST /api/pull` against `http://127.0.0.1:11434`
- defaults to dry-run so the operator can inspect the pull plan first

## Limitations

- The dedicated runtime still depends on the locally installed Ollama binary at:
  `/Applications/Ollama.app/Contents/Resources/ollama`
- Base-model reuse assumes the default blobs remain available in
  `~/.ollama/models/blobs`
- The startup script creates the alias from the checked-in Modelfile through
  Ollama's HTTP API, not through `ollama create`
- If the default runtime is not available and no `phi4-mini` manifest exists in
  `~/.ollama/models/manifests`, the script cannot infer a local base model
- On this host, interactive `ollama` CLI subcommands were observed to be less
  reliable than the HTTP API path in the agent sandbox, so validation relies on
  `/api/tags`, `/api/show`, and `/api/ps`
