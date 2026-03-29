# `voicemode voice` Runtime

This guide covers the new opt-in local/hybrid desktop voice runtime for macOS.
It is designed for explicit turn ownership, cancel-and-replace playback, and
text-first output.

## What It Does

```bash
voicemode voice run
```

The runtime exposes separate control paths for:

- `walkie-talkie` mode with push-to-talk
- `conversational` mode with open-mic interruption support
- interruptible read-aloud for markdown and plain text
- diagnostics and Hammerspoon hotkey export

Keyboard use remains available at all times. Voice is supplementary, not the
source of truth.

## Startup

Recommended startup sequence:

```bash
# Start the runtime
voicemode voice run

# Check current status
voicemode voice status

# Inspect readiness and dependency health
voicemode voice diag
```

## Suggested macOS Components

The runtime is intended to work best with:

- `Pipecat` for optional orchestration adapter hooks
- `whisper.cpp` for local STT
- `Kokoro-FastAPI` for local TTS
- `Ollama` with `phi4-mini` for local voice-shell routing and short summaries
- `Codex` CLI for deep coding or repo work
- `mpv` for cancellable audio playback
- `Hammerspoon` for global hotkeys and mode switching

If `mpv` is missing, the runtime should degrade to text-only output instead of
blocking the workflow.

## Push-To-Talk And Modes

The runtime defaults to walkie-talkie mode. A generated Hammerspoon script can
drive the local control endpoint for:

- PTT down/up
- mode switching
- stop speaking now
- continue reading

Generate a starter config with:

```bash
voicemode voice export-hammerspoon
```

## Configuration

The runtime uses its own `VOICEMODE_RUNTIME_*` namespace so it can coexist with
the older MCP voice settings.

| Variable | Purpose |
| --- | --- |
| `VOICEMODE_RUNTIME_DIR` | Base directory for runtime state |
| `VOICEMODE_RUNTIME_LOG_DIR` | Rotating runtime logs |
| `VOICEMODE_RUNTIME_DB` | SQLite session/event database path |
| `VOICEMODE_RUNTIME_MODE` | `walkie-talkie` or `conversational` |
| `VOICEMODE_RUNTIME_HOST` | Control server host |
| `VOICEMODE_RUNTIME_PORT` | Control server port |
| `VOICEMODE_PTT_HOTKEY` | Hammerspoon hotkey chord |
| `VOICEMODE_RUNTIME_MUTE` | Disable spoken output |
| `VOICEMODE_PIPECAT_ENABLED` | Enable Pipecat adapter health and import checks |
| `VOICEMODE_SUMMARY_THRESHOLD_WORDS` | Switch to spoken summary above this size |
| `VOICEMODE_READ_CHUNK_WORD_LIMIT` | Read-aloud chunk size |
| `VOICEMODE_PREFER_MPV` | Prefer `mpv` playback |
| `VOICEMODE_RUNTIME_TTS_BASE_URL` | OpenAI-compatible TTS endpoint |
| `VOICEMODE_RUNTIME_STT_BASE_URL` | OpenAI-compatible STT endpoint |
| `VOICEMODE_OLLAMA_BASE_URL` | Local Ollama URL |
| `VOICEMODE_OLLAMA_MODEL` | Local voice-shell model |
| `VOICEMODE_RUNTIME_TTS_MODEL` | TTS model name |
| `VOICEMODE_RUNTIME_TTS_VOICE` | Default TTS voice |
| `VOICEMODE_CODEX_COMMAND` | Command template for the Codex bridge |
| `VOICEMODE_VAD_BACKEND` | `auto`, `silero`, `webrtc`, or `energy` |
| `VOICEMODE_VAD_AGGRESSIVENESS` | WebRTC VAD aggressiveness (0-3) |
| `VOICEMODE_VAD_SILENCE_FRAMES` | Consecutive silent frames before end-of-speech |
| `VOICEMODE_VAD_ENERGY_THRESHOLD` | Energy fallback threshold |
| `VOICEMODE_TIMEOUT_RECORDING` | Recording timeout |
| `VOICEMODE_TIMEOUT_STT` | Transcription timeout |
| `VOICEMODE_TIMEOUT_ROUTING` | Routing timeout |
| `VOICEMODE_TIMEOUT_LOCAL_LLM` | Local voice-shell timeout |
| `VOICEMODE_TIMEOUT_CODEX` | Codex timeout |
| `VOICEMODE_TIMEOUT_TTS_GENERATION` | TTS generation timeout |
| `VOICEMODE_TIMEOUT_PLAYBACK` | Playback timeout |

## Runtime Behavior

The runtime is intentionally cancel-first:

- user speech interrupts assistant audio immediately
- new turns replace the current turn instead of queueing behind it
- long spoken answers are summarized automatically
- markdown and file reading are chunked and resumable
- text output stays primary

## Diagnostics

Useful commands:

```bash
voicemode voice status
voicemode voice diag
```

Diagnostics should report:

- current mode
- current state
- recent events
- persisted runtime summary from SQLite, including session/event counts and recent read-progress
- health of conversational VAD, Pipecat, Whisper, Kokoro, Ollama, Codex, `mpv`, and Hammerspoon

The generated Hammerspoon config now also renders clearer menubar state labels
such as `VM LISTEN`, `VM THINK`, `VM SPEAK`, and `VM READ`, plus a tooltip with
mode, state, mute status, and the active reading document.

## Current Boundaries

Phase 3 is complete for the current repo/runtime scope. The runtime remains
intentionally conservative in v1:

- conversational mode now supports `silero`, `webrtc`, and `energy` backends
- `auto` prefers Silero when available, then falls back to WebRTC and energy
- the stable runtime still keeps the explicit native turn manager as the primary orchestrator, with Pipecat available through an adapter surface instead of replacing state ownership
- RNNoise and echo cancellation are optional later hardening work
- the Hammerspoon script is a starter config, not a full desktop app
- timeout and failure recovery now keep the runtime usable, but broader live recovery coverage still needs expansion
- cloud Codex integration is represented as a CLI bridge, not a native SDK path
- richer document parsing can come later if read-aloud needs expand

## Related Docs

- [Getting Started](../tutorials/getting-started.md)
- [Configuration Guide](configuration.md)
- [VoiceMode Architecture](../concepts/architecture.md)
