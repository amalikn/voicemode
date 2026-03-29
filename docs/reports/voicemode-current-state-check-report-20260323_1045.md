# VoiceMode Current-State Check Report

## Scope

This report covers the live local checkout at `/Volumes/Data/_ai/_mcp/mcp_stuff/voicemode`.

The goal was to run the currently testable runtime checks end to end and report the usable boundary of the new `voicemode voice` runtime and its Codex-facing setup.

## Assumptions

- "Current state" means the local working tree as checked out now, not a future commit.
- The repo is currently on `HEAD` commit `ece9eae` with substantial uncommitted local changes on top.
- Existing dirty working-tree changes were not reverted or normalized before testing.

## Findings

- The renamed package surface is operational:
  - `uv run voicemode --help` works
  - `uv run voicemode voice --help` works
  - the internal package imports resolve as `python_voicemode`
- The realtime readiness check succeeds partially:
  - `whisper.cpp` reachable
  - `kokoro` reachable
  - `ollama` reachable
  - `codex` available
  - `hammerspoon` missing
  - `mpv` missing
- The daemon startup path works:
  - `uv run voicemode voice run` started successfully
  - the control server bound to `127.0.0.1:8766`
- The live control/status path works:
  - `uv run voicemode voice status` returned runtime state
  - `uv run voicemode voice control MODE_SWITCH --mode conversational` was accepted
  - follow-up status showed the mode changed to `conversational`
- The read-aloud path is not currently healthy:
  - `uv run voicemode voice read README.md` failed with HTTP `500`
  - daemon traceback shows a runtime bug:
    - `AttributeError: 'ReadDocument' object has no attribute 'current_chunk'`
  - the failing path is in `python_voicemode/realtime/turn_manager.py`
- The focused automated realtime test slice passes:
  - `uv run pytest -o addopts='' tests/realtime -q` -> `14 passed, 1 warning`
- Codex configuration is only partially ready:
  - `codex mcp list` shows `voicemode` configured at `http://127.0.0.1:8765/mcp`
  - the MCP endpoint is not actually serving right now
  - `curl http://127.0.0.1:8765/health` failed to connect

## Direct Edits Required

None for the checks themselves.

This report does not include a code fix for the `read-file` failure.

## Impacted Consumers

- Repo-local CLI/runtime testing is currently possible for:
  - readiness
  - daemon startup
  - control events
  - status inspection
- End-to-end desktop voice UX is still limited by missing host dependencies:
  - `hammerspoon`
  - `mpv`
- Codex users do not currently get a live `voicemode` MCP server just from config presence because the endpoint on `8765` is down.
- Read-aloud consumers are currently blocked by the `ReadDocument.current_chunk` bug.

## Validation

Verified directly:

- `git rev-parse --short HEAD` -> `ece9eae`
- `uv run voicemode --help`
- `uv run voicemode voice --help`
- `uv run voicemode voice diag`
- `uv run voicemode voice run`
- `lsof -nP -iTCP:8766 -sTCP:LISTEN`
- `uv run voicemode voice status`
- `uv run voicemode voice control MODE_SWITCH --mode conversational`
- `uv run voicemode voice status` after mode switch
- `uv run voicemode voice read README.md`
- daemon-side traceback from the running runtime session
- `uv run pytest -o addopts='' tests/realtime -q` -> `14 passed, 1 warning`
- `codex mcp list`
- `curl -sS -D - http://127.0.0.1:8765/health`

Not validated in this pass:

- live push-to-talk hotkeys through Hammerspoon
- cancellable playback through `mpv`
- true end-to-end conversational barge-in with real audio playback
- MCP traffic through a running VoiceMode server on `8765`

## Risks / Caveats

- The repo is still in a dirty working-tree state during this check.
- The read-aloud HTTP `500` is a real runtime defect, not just a missing dependency.
- The runtime status after switching to conversational mode showed:
  - `state: LISTENING`
  - `reading_document: README.md`
  - `last_transcript: [BLANK_AUDIO]`
  - `muted: true`
  This is worth reviewing during runtime hardening, but it did not block the specific control-path check.
- `pytest` required `-o addopts=''` because the repo pytest configuration references options not available in the current environment.

## Final Answer

The current state is good enough to test:

- package importability
- CLI entrypoints
- readiness checks
- daemon startup
- control/status flow
- focused realtime unit/integration tests

The current state is not yet good enough to claim full runtime readiness because:

- read-aloud currently fails with a server-side bug
- `mpv` and `hammerspoon` are not installed
- the Codex-facing MCP endpoint on `127.0.0.1:8765` is configured but not live

## Key Evidence

- Realtime control server: listening on `127.0.0.1:8766`
- Realtime tests: `14 passed, 1 warning`
- Read-aloud failure:
  - `AttributeError: 'ReadDocument' object has no attribute 'current_chunk'`
- Codex MCP boundary:
  - configured: yes
  - live on `8765`: no
