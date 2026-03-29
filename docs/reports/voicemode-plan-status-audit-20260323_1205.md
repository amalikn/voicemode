# VoiceMode Plan Status Audit

## Scope

This audit compares the requested local/hybrid voice-runtime plan against the
current live repo state in `/Volumes/Data/_ai/_mcp/mcp_stuff/voicemode`.

It is a status report, not a fresh implementation pass.

## Assumptions

- The authoritative implementation surface is the current working tree, not
  just the earlier plan text.
- Existing outcome and runtime-check reports are informative, but code and live
  checks take precedence where they disagree.
- Branding remains `voicemode` / `voice-mode`; internal Python package surface
  is now `python_voicemode`.

## Overall Status

- `Phase 1`: mostly implemented
- `Phase 2`: partially implemented
- `Phase 3`: partially implemented

Best honest label:

- The explicit runtime architecture exists.
- The MCP/server path is usable.
- The desktop voice workflow is not yet production-ready end to end.

## What Is Implemented

### Core explicit runtime

Implemented in `python_voicemode.realtime`:

- explicit interaction modes:
  - `walkie-talkie`
  - `conversational`
- explicit runtime states:
  - `IDLE`
  - `LISTENING`
  - `RECORDING`
  - `TRANSCRIBING`
  - `ROUTING`
  - `WAITING_LOCAL`
  - `WAITING_CODEX`
  - `PLAYING_TTS`
  - `READING_CHUNK`
  - `INTERRUPTED`
  - `ERROR`
- explicit event types for PTT, VAD, routing, TTS, barge-in, read controls,
  timeout, and failure
- per-stage timeout model

Evidence:

- `python_voicemode/realtime/models.py`

### Turn ownership and cancel-and-replace

Implemented:

- one turn manager controlling capture, routing, playback, and interruptions
- `ptt_down()` forces barge-in before recording
- `stop_speaking()` forces barge-in and transitions away from playback
- `_barge_in()` stops audio, cancels the active task, and records the event
- no queue-based speech recovery is visible in the realtime runtime

Evidence:

- `python_voicemode/realtime/turn_manager.py`

### Local control daemon

Implemented:

- local aiohttp control server
- `/status`
- `/diag`
- `/control`
- `/read-file`
- `/hammerspoon/export`
- conversational open-mic loop with VAD frame processing

Evidence:

- `python_voicemode/realtime/orchestrator.py`

### CLI surface

Implemented:

- `voicemode voice run`
- `voicemode voice status`
- `voicemode voice diag`
- `voicemode voice control`
- `voicemode voice read`
- `voicemode voice export-hammerspoon`

Evidence:

- `python_voicemode/cli_commands/voice.py`
- `python_voicemode/cli.py`

### Read-aloud subsystem

Implemented structurally:

- markdown stripping
- paragraph/section-style chunking by word limit
- persisted cursor state
- continue/repeat/skip/summarize/stop controller methods

Evidence:

- `python_voicemode/realtime/read_aloud.py`

### Session/event persistence and diagnostics

Implemented:

- SQLite-backed `sessions`, `events`, and `read_progress`
- runtime status and diagnostic views include recent events and dependency health

Evidence:

- `python_voicemode/realtime/session_store.py`
- `python_voicemode/realtime/orchestrator.py`
- `python_voicemode/realtime/launcher.py`

### Local/remote routing structure

Implemented:

- local route
- Codex route
- read-aloud route
- spoken-output planning and summary mode support
- local Ollama-based voice-shell helper
- command-template Codex bridge

Evidence:

- `python_voicemode/realtime/router.py`
- `python_voicemode/realtime/summary.py`
- `python_voicemode/realtime/voice_shell.py`
- `python_voicemode/realtime/codex_bridge.py`

### Hammerspoon starter integration

Implemented partially:

- generated Hammerspoon config
- hotkey bindings
- menubar status item in generated Lua

Evidence:

- `python_voicemode/realtime/ptt.py`

### Tests

Implemented:

- focused realtime tests for turn manager, read-aloud, router/models, session
  store, and CLI

Evidence:

- `tests/realtime/test_turn_manager.py`
- `tests/realtime/test_read_aloud.py`
- `tests/realtime/test_models_router.py`
- `tests/realtime/test_session_store.py`
- `tests/realtime/test_cli_voice.py`

## What Is Implemented But Still Limited

### Launcher/readiness

Present, but still mostly a readiness checker:

- health checks for `hammerspoon`, `mpv`, `whisper.cpp`, `kokoro`, `ollama`,
  and Codex
- directory initialization and runtime wiring

Limitation:

- it does not fully auto-install or fully auto-start the full stack as a single
  stable launcher experience

Evidence:

- `python_voicemode/realtime/launcher.py`
- `python_voicemode/realtime/config.py`

### Conversational mode

Present, but not hardened:

- open-mic loop exists
- VAD transitions exist
- barge-in path exists

Limitation:

- VAD is still an energy-gate fallback, not true Silero-based production
  streaming behavior

Evidence:

- `python_voicemode/realtime/orchestrator.py`
- `python_voicemode/realtime/vad.py`

### mpv support

Present as an adapter:

- `MpvAudioPlayer` supports killable playback

Limitation:

- runtime falls back to `NullAudioPlayer` when `mpv` is absent
- live playback behavior is therefore host-dependent and not universally ready

Evidence:

- `python_voicemode/realtime/audio.py`

### Codex bridge

Present structurally:

- command-template execution with timeout handling
- health check for Codex CLI availability

Limitation:

- still a CLI adapter rather than a deeply integrated validated daemon-to-Codex
  workflow
- prior reports note end-to-end validation remains pending

Evidence:

- `python_voicemode/realtime/codex_bridge.py`
- `voicemode-voice-runtime-implementation-outcome-20260323_1029.md`

## What Is Broken

### Read-aloud live path

The live read command is currently broken.

Contradiction:

- `ReadAloudController` exposes `current_chunk()`
- `TurnManager.read_file()` calls `document.current_chunk()`

That mismatch causes the live `voicemode voice read <file>` path to fail.

Evidence:

- `python_voicemode/realtime/read_aloud.py`
- `python_voicemode/realtime/turn_manager.py`
- `voicemode-current-state-check-report-20260323_1045.md`

## What Is Still Pending

### Pipecat orchestration

Pending.

Repo-wide search found no Pipecat integration in code or docs as an implemented
 dependency.

Evidence:

- repo search for `pipecat` / `Pipecat` returned no hits

### Silero VAD integration

Pending / deferred.

Silero appears only as:

- docs describing it as a follow-up
- a comment in `realtime/vad.py` saying the current class can be extended later

Evidence:

- `python_voicemode/realtime/vad.py`
- `docs/guides/voice-runtime.md`
- `voicemode-voice-runtime-implementation-outcome-20260323_1029.md`

### Hammerspoon live integration

Pending.

What exists is export/generation of a starter config, not a full installed and
verified hotkey subsystem.

Evidence:

- `python_voicemode/realtime/ptt.py`
- `python_voicemode/cli_commands/voice.py`

### True production walkie-talkie UX

Pending.

PTT control semantics exist in code, but global hotkey capture and fully
verified desktop interaction are still host/setup dependent.

Evidence:

- `python_voicemode/realtime/turn_manager.py`
- `python_voicemode/realtime/ptt.py`

### Production conversational UX

Pending.

The loop exists, but the requested “natural, interruptible, low-latency”
quality bar is not yet met because:

- Silero is not fully integrated
- `mpv` is not guaranteed/verified everywhere
- Hammerspoon is not fully installed/verified

Evidence:

- `python_voicemode/realtime/orchestrator.py`
- `python_voicemode/realtime/vad.py`
- `voicemode-current-state-check-report-20260323_1045.md`

### RNNoise / echo cancellation

Pending.

Only mentioned in docs as later hardening.

Evidence:

- `docs/guides/voice-runtime.md`

### Menubar/status polish

Partially present as a Hammerspoon menubar item, but not a finished polished
desktop status surface.

Evidence:

- `python_voicemode/realtime/ptt.py`

## Phase-by-Phase Assessment

### Phase 1

Requested:

- launcher
- PTT
- whisper.cpp
- Kokoro playback
- stop-on-barge-in
- state machine
- keyboard + text in parallel

Status:

- implemented in structure: launcher, state machine, stop-on-barge-in,
  whisper/kokoro adapters, keyboard/text-first design
- partially implemented: PTT depends on Hammerspoon starter config and host
  setup
- not fully production-ready: live playback path depends on `mpv`

Verdict:

- `Phase 1` is mostly implemented, but not fully hardened on a fresh host.

### Phase 2

Requested:

- Pipecat orchestration
- Silero VAD conversational mode
- local Phi-4-mini voice shell
- Codex escalation path
- summary-mode speech

Status:

- implemented: local voice-shell structure, Codex bridge structure,
  summary-mode planning
- partially implemented: conversational mode exists but uses energy-gate VAD
- pending: Pipecat integration
- pending/hardening: true Silero streaming behavior and validated end-to-end
  Codex escalation

Verdict:

- `Phase 2` is partially implemented.

### Phase 3

Requested:

- read-aloud subsystem
- SQLite diagnostics
- menubar/status polish
- resilience hardening
- tests/docs cleanup

Status:

- implemented: read-aloud subsystem structure, SQLite session/event store,
  focused realtime tests, docs
- partially implemented: menubar/status via starter Hammerspoon output
- not complete: resilience hardening
- broken: live read-aloud path currently fails

Verdict:

- `Phase 3` has meaningful implementation, but it is not complete and contains
  at least one live defect.

## Current Best Summary

Where the plan stands right now:

- The repo already contains the explicit event-driven runtime architecture the
  plan asked for.
- The old monolithic `converse` path has not been replaced; a parallel runtime
  was added beside it.
- The biggest wins already implemented are:
  - explicit turn/state modeling
  - cancel-and-replace/barge-in logic
  - local control daemon
  - SQLite-backed event history
  - local/Codex/read routing structure
  - focused tests and docs
- The biggest items still pending are:
  - Pipecat
  - real Silero integration
  - fully installed/verified Hammerspoon
  - fully installed/verified `mpv`
  - live read-aloud bug fix
  - end-to-end desktop UX hardening

Best honest phase label:

- `Phase 1`: mostly implemented
- `Phase 2`: partially implemented
- `Phase 3`: partially implemented

If a single shorthand is needed:

- mid-to-late prototype with a real runtime architecture, not yet production-complete desktop voice UX
