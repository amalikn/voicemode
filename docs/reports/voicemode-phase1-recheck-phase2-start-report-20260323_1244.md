# VoiceMode Phase 1 Recheck And Phase 2 Start Report

## Scope

This report covers two tasks on the live checkout at
`/Volumes/Data/_ai/_mcp/mcp_stuff/voicemode`:

- re-run the concrete Phase 1 checks and confirm they still pass
- start Phase 2 with the smallest high-value implementation slice that improves
  conversational behavior without pretending the entire phase is complete

## Assumptions

- Phase 1 confirmation should remain evidence-based and rerun, not inherited from
  the previous report
- Phase 2 should start with a bounded runtime improvement rather than a large
  orchestration rewrite
- Pipecat is still absent, so a stable conversational VAD/backend upgrade is the
  most defensible next implementation slice

## Findings

### Phase 1 still passes

Rechecked successfully:

- realtime test suite
- Python syntax compilation across `python_voicemode` and `tests`
- `git diff --check`
- runtime readiness via `voicemode voice diag`

The Phase 1 dependency/readiness surface remains green:

- `hammerspoon`
- `mpv`
- `vad`
- `whisper.cpp`
- `kokoro`
- `ollama`
- `codex`

### Phase 2 has now started

Implemented in this pass:

- backend-selectable conversational VAD in `python_voicemode/realtime/vad.py`
- runtime wiring for configurable VAD backend/aggressiveness/silence frames in
  `python_voicemode/realtime/config.py` and
  `python_voicemode/realtime/orchestrator.py`
- VAD health visibility in `python_voicemode/realtime/launcher.py`
- short local Codex-wait acknowledgment playback in
  `python_voicemode/realtime/turn_manager.py`
- docs update in `docs/guides/voice-runtime.md`
- new realtime tests in `tests/realtime/test_vad.py`
- expanded config and Codex-ack coverage in:
  - `tests/realtime/test_models_router.py`
  - `tests/realtime/test_turn_manager.py`

### What changed behaviorally

- conversational mode no longer relies only on the old energy-gate placeholder
- the runtime now supports `VOICEMODE_VAD_BACKEND=auto|webrtc|energy`
- `auto` currently selects `webrtcvad` when available, then falls back to energy
- runtime diagnostics now expose the active VAD backend explicitly
- when a request routes to Codex, the local voice shell can now give a short
  spoken acknowledgment while the deeper answer is being fetched

### What did not happen yet

- Pipecat is still not implemented
- true Silero stream integration is still not active in the runtime path
- the `livekit` / Silero dependency path was installed, but this pass stopped at
  a stable WebRTC-backed conversational VAD improvement rather than forcing a
  riskier incomplete Silero stream adapter

## Direct edits required

Completed in this pass:

- `python_voicemode/realtime/config.py`
- `python_voicemode/realtime/vad.py`
- `python_voicemode/realtime/orchestrator.py`
- `python_voicemode/realtime/launcher.py`
- `python_voicemode/realtime/turn_manager.py`
- `tests/realtime/test_models_router.py`
- `tests/realtime/test_turn_manager.py`
- `tests/realtime/test_vad.py`
- `docs/guides/voice-runtime.md`
- `uv sync --extra livekit`

## Impacted consumers

- conversational runtime users now get a stronger VAD path than the old
  energy-only placeholder
- operators running `voicemode voice diag` now see the active VAD backend
- Codex-routed requests can produce a short local acknowledgment before the deep
  response arrives

CLI command names did not change in this pass.

## Validation

Validated directly:

- `uv run pytest -o addopts='' tests/realtime -q`
  - result: `19 passed, 1 warning`
- `python3 -m py_compile $(find python_voicemode tests -name '*.py' -type f)`
- `git diff --check`
- `uv run voicemode voice diag`
  - result included `OK   vad          webrtc: webrtcvad aggressiveness=2`

## Risks / caveats

- Phase 2 is started, not complete
- Pipecat remains missing
- Silero packages are now installed, but the active runtime backend is still the
  stable WebRTC implementation rather than a full Silero stream adapter
- this pass prioritized a reliable conversational improvement over a risky,
  partially understood Silero stream integration

## Final answer

Phase 1 still passes cleanly.

Phase 2 has now started with a real runtime improvement:

- conversational VAD is backend-selectable and no longer just an energy-only
  placeholder
- diagnostics expose the active VAD backend
- Codex routes now support a short local acknowledgment while waiting

The next Phase 2 step should be true Silero-backed stream integration behind the
same VAD interface, followed by deeper live validation of the Codex escalation
path under real conversational-mode traffic.
