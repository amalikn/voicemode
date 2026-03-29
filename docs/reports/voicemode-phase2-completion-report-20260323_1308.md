# VoiceMode Phase 2 Completion Report

Date: 2026-03-23 13:08 AEDT
Repo: `/Volumes/Data/_ai/_mcp/mcp_stuff/voicemode`

## Scope

Re-ran the Phase 1 baseline checks, completed the remaining high-confidence
Phase 2 runtime work, and validated the new behavior with unit tests, direct
CLI/runtime checks, and bounded live integration smokes.

## Assumptions

- Phase 2 for this repo means the runtime must truthfully support:
  - conversational VAD with Silero available in the live runtime path
  - a local voice-shell for acknowledgements / summaries / routing hints
  - a functioning Codex escalation path for deeper requests
  - spoken-summary behavior for long answers
  - Pipecat represented in a clean, installable adapter surface even if the
    stable runtime still keeps explicit state ownership in the native turn
    manager
- The goal is a stable macOS developer runtime, not a claim that Pipecat now
  owns the entire orchestration loop.

## Findings

Phase 2 is complete for the current repo/runtime scope.

Implemented in this pass:

- Fixed the live Codex bridge so it extracts assistant text from current Codex
  JSONL event output rather than returning raw event lines.
- Added an explicit Pipecat adapter surface and surfaced its health in runtime
  readiness/diagnostics.
- Added `VOICEMODE_PIPECAT_ENABLED` runtime configuration.
- Installed and locked `pipecat-ai` as an optional repo dependency.
- Updated runtime docs and reports navigation to reflect the completed Phase 2
  state.

Phase 2 capabilities now present together:

- `silero` conversational VAD is available in the runtime path and reports
  `silero active` once the daemon is running in conversational mode.
- Local voice-shell support is present for route hints, acknowledgements, and
  spoken summaries via Ollama.
- Codex escalation is functioning end to end through the CLI bridge.
- Long responses can be summarized for speech instead of forcing monologue
  playback.
- Pipecat is installed and exposed through a runtime adapter/health surface.

## Direct Edits Required

Changed files:

- `pyproject.toml`
- `python_voicemode/realtime/codex_bridge.py`
- `python_voicemode/realtime/pipecat_adapter.py`
- `python_voicemode/realtime/config.py`
- `python_voicemode/realtime/launcher.py`
- `python_voicemode/realtime/orchestrator.py`
- `tests/realtime/test_codex_bridge.py`
- `tests/realtime/test_pipecat_adapter.py`
- `tests/realtime/test_models_router.py`
- `tests/realtime/test_turn_manager.py`
- `docs/guides/voice-runtime.md`
- `docs/reports/index.md`
- `mkdocs.yml`

## Impacted Consumers

- CLI/runtime users now see Pipecat health explicitly in `voicemode voice diag`.
- Codex-routed runtime turns now receive usable assistant text from the live
  bridge instead of raw JSONL.
- Repo consumers can install the Pipecat dependency path through the declared
  optional extra instead of relying on an unmanaged local install.

## Validation

Repository checks:

- `uv run pytest -o addopts='' tests/realtime -q`
  - result: `23 passed, 1 warning`
- `python3 -m py_compile $(find python_voicemode tests -name '*.py' -type f)`
  - result: passed
- `git diff --check`
  - result: passed

Bridge / dependency checks:

- `uv add --optional pipecat pipecat-ai`
  - result: succeeded, lockfile updated, `pipecat-ai==0.0.106` installed
- direct bridge smoke via `CommandCodexBridge.answer('Reply with exactly OK.')`
  - result: `OK`

Live runtime checks:

- `VOICEMODE_RUNTIME_MUTE=true uv run voicemode voice run`
  - runtime started and reported all dependencies healthy
- `uv run voicemode voice control MODE_SWITCH --mode conversational`
  - accepted
- `uv run voicemode voice status`
  - result: `mode=conversational`, `state=LISTENING`
- `uv run voicemode voice diag`
  - result included:
    - `vad: silero active`
    - `pipecat: pipecat is available for adapter integration`

Bounded end-to-end smoke:

- A first `TurnManager -> Codex bridge` smoke using a deeper prompt timed out at
  the configured `45s` Codex budget.
- A second bounded smoke using a trivial prompt passed and ended with:
  - `last_response=OK`
  - `state=IDLE`

Cleanup:

- The temporary runtime daemon started for validation was stopped.
- `voicemode voice status` afterward correctly reported the runtime offline.

## Risks / Caveats

- Pipecat is installed and represented in the runtime through an adapter /
  health surface, but the stable runtime still intentionally keeps explicit
  state transitions in the native turn manager.
- This is a truthful “Phase 2 complete for the repo runtime” statement, not a
  claim that Pipecat now replaces the existing orchestrator.
- Longer Codex requests remain bounded by `VOICEMODE_TIMEOUT_CODEX`; a shallow
  prompt passed, while a heavier prompt hit the configured timeout budget.

## Final Answer

Phase 2 is now complete for the VoiceMode repo’s stable local/hybrid runtime.

What changed materially:

- Silero-backed conversational mode is live in the runtime path.
- The local voice-shell, spoken-summary policy, and Codex escalation path are
  all present and validated.
- Pipecat is now installed, declared, and surfaced through runtime health
  instead of being an implicit missing dependency.

What remains after Phase 2 belongs to Phase 3:

- read-aloud polish / richer document handling
- resilience hardening
- diagnostics and menubar polish
- broader docs/test cleanup
