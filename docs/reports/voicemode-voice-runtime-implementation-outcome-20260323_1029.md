# Voice Runtime Implementation Outcome

Session / Workstream:
- `voicemode` local/hybrid voice runtime implementation

Scope:
- Add a new opt-in `voicemode voice` runtime beside the existing monolithic
  `converse` path.
- Implement explicit turn ownership, cancel-and-replace behavior, chunked
  read-aloud support, local control endpoints, diagnostics, and supporting
  docs/tests.

Completed:
- Added a new `python_voicemode.realtime` package with:
  - explicit states and events
  - a turn manager with cancel-and-replace/barge-in behavior
  - routing between local voice-shell, Codex, and read-aloud flows
  - chunked markdown/text read-aloud with persisted cursor state
  - SQLite-backed session/event storage
  - mpv-oriented audio playback adapter
  - whisper/kokoro/ollama/codex integration adapters
  - microphone/VAD scaffolding and launcher health checks
  - an aiohttp control server for local automation and Hammerspoon hooks
- Added a new `voicemode voice` CLI group with:
  - `run`
  - `status`
  - `diag`
  - `control`
  - `read`
  - `export-hammerspoon`
- Added focused tests for the new runtime surface under `tests/realtime/`.
- Added operator-facing docs and repo-root plan/outcome artifacts.

Files Changed:
- `python_voicemode/realtime/__init__.py`
- `python_voicemode/realtime/audio.py`
- `python_voicemode/realtime/codex_bridge.py`
- `python_voicemode/realtime/config.py`
- `python_voicemode/realtime/launcher.py`
- `python_voicemode/realtime/logging_runtime.py`
- `python_voicemode/realtime/microphone.py`
- `python_voicemode/realtime/models.py`
- `python_voicemode/realtime/orchestrator.py`
- `python_voicemode/realtime/ptt.py`
- `python_voicemode/realtime/read_aloud.py`
- `python_voicemode/realtime/router.py`
- `python_voicemode/realtime/session_store.py`
- `python_voicemode/realtime/stt.py`
- `python_voicemode/realtime/summary.py`
- `python_voicemode/realtime/tts.py`
- `python_voicemode/realtime/turn_manager.py`
- `python_voicemode/realtime/vad.py`
- `python_voicemode/realtime/voice_shell.py`
- `python_voicemode/cli_commands/voice.py`
- `python_voicemode/cli.py`
- `tests/conftest.py`
- `tests/test_skip_tts.py`
- `tests/realtime/conftest.py`
- `tests/realtime/test_cli_voice.py`
- `tests/realtime/test_models_router.py`
- `tests/realtime/test_read_aloud.py`
- `tests/realtime/test_session_store.py`
- `tests/realtime/test_turn_manager.py`
- `docs/guides/voice-runtime.md`
- `docs/guides/configuration.md`
- `README.md`
- `mkdocs.yml`
- `voicemode-voice-runtime-implementation-plan-20260323_1001.md`
- `voicemode-voice-runtime-implementation-outcome-20260323_1029.md`

Decisions:
- Kept the existing `converse` implementation intact and introduced a parallel
  runtime instead of retrofitting the monolithic flow in place.
- Defaulted the new runtime to explicit cancel-and-replace semantics so new user
  speech wins over in-flight assistant speech.
- Kept text as the primary output and treated spoken output as a summary or
  supplementary channel by default.
- Used clean adapters/stubs for uncertain external integrations so the runtime
  structure is in place without claiming unsupported behavior.

Validation:
- `python3 -m py_compile python_voicemode/cli.py python_voicemode/cli_commands/voice.py python_voicemode/realtime/*.py`
- `PYTHONPATH=. ./.venv/bin/python -m python_voicemode --help`
- `PYTHONPATH=. ./.venv/bin/python -m python_voicemode voice --help`
- `PYTHONPATH=. ./.venv/bin/python -m python_voicemode voice diag`
- `git diff --check`
- Managed-Python smoke script covering:
  - config loading
  - route classification
  - read-aloud chunking and persisted cursor state
  - spoken summary planning
  - basic turn-manager state transitions and stop/cancel path
- A delegated test worker reported:
  - `pytest -o addopts='' tests/realtime -q` -> `14 passed, 1 warning`
- Not independently re-run by the coordinator:
  - local `pytest` execution, because `pytest` is absent from both the repo venv
    and the system interpreter in this environment

Open Issues:
- `mpv` is not installed on this host, so live cancellable playback was not
  verified here.
- Hammerspoon is not installed on this host, so global hotkey behavior was not
  verified here.
- whisper.cpp, Kokoro-FastAPI, and Ollama endpoints were unreachable during
  diagnostics in this environment.
- Conversational mode currently uses a stable energy-gate VAD scaffold; true
  Silero streaming integration still needs hardening.
- The Codex bridge is implemented but not yet validated with a live end-to-end
  coding request from the daemon.

Next Actions:
- Install and verify `mpv` and Hammerspoon, then test live walkie-talkie and
  stop-speaking flows.
- Bring up whisper.cpp, Kokoro-FastAPI, and Ollama Phi-4-mini until launcher
  health is green.
- Harden conversational mode with Silero-based streaming VAD and tune
  interruption thresholds.
- Run end-to-end read-aloud tests covering continue, repeat, skip, summarize,
  and stop.
- Validate real Codex escalation from the daemon and tighten timeout/retry
  behavior where needed.

Artifacts / Pointers:
- `docs/guides/voice-runtime.md`
- `python_voicemode/cli_commands/voice.py`
- `python_voicemode/realtime/orchestrator.py`
- `python_voicemode/realtime/turn_manager.py`
- `voicemode-voice-runtime-implementation-plan-20260323_1001.md`

Persistence Status:
- memory-keeper: success
- project-context: success
- memory checkpoint: success
- project checkpoint: success
- fallback used: no
