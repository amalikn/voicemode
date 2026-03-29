import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from python_voicemode.realtime.config import RealtimeVoiceConfig
from python_voicemode.realtime.models import RouteTarget, SpokenOutputMode, VoiceEventType, VoiceMode, VoiceState
from python_voicemode.realtime.models import StageTimeouts
from python_voicemode.realtime.read_aloud import ReadAloudController
from python_voicemode.realtime.session_store import SessionStore
from python_voicemode.realtime.summary import SpokenResponsePlanner
from python_voicemode.realtime.turn_manager import TurnManager


class FakeRecorder:
    def __init__(self):
        self.started = False
        self.active = False
        self.calls = []

    def start(self):
        self.started = True
        self.active = True

    def stop(self, path: Path):
        self.calls.append(path)
        self.active = False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("wave")
        return path


class FakePlayer:
    def __init__(self):
        self.stopped = 0
        self.played = []
        self.waited = 0
        self.available = True

    def is_available(self):
        return self.available

    async def play(self, audio_path: Path):
        self.played.append(audio_path)

    async def stop(self):
        self.stopped += 1

    async def wait(self, timeout=None):
        self.waited += 1


class FakeSTT:
    def __init__(self, transcript="hello from stt"):
        self.transcript = transcript

    async def transcribe_file(self, audio_path: Path):
        return self.transcript


class SlowSTT(FakeSTT):
    async def transcribe_file(self, audio_path: Path):
        await asyncio.sleep(0.05)
        return self.transcript


class FakeTTS:
    def __init__(self):
        self.calls = []

    async def synthesize_to_file(self, text: str, output_path: Path):
        self.calls.append(text)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text)
        return output_path


class FailingTTS(FakeTTS):
    async def synthesize_to_file(self, text: str, output_path: Path):
        raise RuntimeError("tts backend unavailable")


class FakeVoiceShell:
    def __init__(self):
        self.answers = []
        self.acks = []

    async def answer_short(self, text: str):
        self.answers.append(text)
        return "short response"

    async def acknowledge(self, text: str):
        self.acks.append(text)
        return "Checking that."

    async def summarize_for_speech(self, text: str):
        return f"summary: {text[:20]}"


class FakeCodexBridge:
    def __init__(self):
        self.prompts = []

    async def answer(self, prompt: str, timeout: float):
        self.prompts.append((prompt, timeout))
        return "codex response"


class FakeRouter:
    def __init__(self, target=RouteTarget.LOCAL, command=None):
        self.target = target
        self.command = command
        self.calls = []

    async def decide(self, text: str, read_aloud_active: bool = False):
        self.calls.append((text, read_aloud_active))
        return SimpleNamespace(target=self.target, reason="test", command=self.command)


def build_config(tmp_path: Path, mode: VoiceMode = VoiceMode.WALKIE_TALKIE) -> RealtimeVoiceConfig:
    return RealtimeVoiceConfig(
        workspace_dir=tmp_path,
        runtime_dir=tmp_path / "runtime",
        logs_dir=tmp_path / "runtime" / "logs",
        recordings_dir=tmp_path / "runtime" / "recordings",
        tts_dir=tmp_path / "runtime" / "tts",
        session_db_path=tmp_path / "runtime" / "sessions.sqlite3",
        control_host="127.0.0.1",
        control_port=8766,
        mode=mode,
        ptt_hotkey="cmd+shift+space",
        mute_voice_output=False,
        summary_threshold_words=5,
        read_chunk_word_limit=6,
        prefer_mpv=False,
        auto_start_local_services=False,
        start_conversational_on_launch=False,
        pipecat_enabled=False,
        tts_base_url="http://127.0.0.1:8880/v1",
        stt_base_url="http://127.0.0.1:2022/v1",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="phi4-mini",
        kokoro_model="tts-1",
        kokoro_voice="af_sky",
        codex_command="codex exec --json --skip-git-repo-check -C {workspace}",
        vad_backend="auto",
        vad_aggressiveness=2,
        vad_silence_frames=15,
        vad_energy_threshold=0.012,
        stage_timeouts=StageTimeouts(),
    )


@pytest.mark.asyncio
async def test_ptt_barge_in_cancels_audio_and_transitions_to_recording(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    recorder = FakeRecorder()
    player = FakePlayer()
    turn_manager = TurnManager(
        config=build_config(tmp_path),
        session_store=store,
        recorder=recorder,
        stt=FakeSTT(),
        tts=FakeTTS(),
        player=player,
        router=FakeRouter(),
        planner=SpokenResponsePlanner(5, FakeVoiceShell()),
        voice_shell=FakeVoiceShell(),
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 6),
    )

    await turn_manager._transition(VoiceState.PLAYING_TTS, VoiceEventType.TTS_START, {})
    await turn_manager.ptt_down()

    assert player.stopped == 1
    assert recorder.started is True
    assert turn_manager.state == VoiceState.RECORDING


@pytest.mark.asyncio
async def test_ptt_turn_transcribes_routes_and_plays_local_response(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    recorder = FakeRecorder()
    player = FakePlayer()
    voice_shell = FakeVoiceShell()
    turn_manager = TurnManager(
        config=build_config(tmp_path),
        session_store=store,
        recorder=recorder,
        stt=FakeSTT("please help me"),
        tts=FakeTTS(),
        player=player,
        router=FakeRouter(RouteTarget.LOCAL),
        planner=SpokenResponsePlanner(5, voice_shell),
        voice_shell=voice_shell,
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 6),
    )

    await turn_manager.ptt_down()
    await turn_manager.ptt_up()
    assert turn_manager._active_task is not None
    await turn_manager._active_task

    assert voice_shell.answers == ["please help me"]
    assert player.played, "expected TTS playback to be invoked"
    assert turn_manager.last_transcript == "please help me"


@pytest.mark.asyncio
async def test_codex_route_uses_bridge_and_summary_mode(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    recorder = FakeRecorder()
    player = FakePlayer()
    codex = FakeCodexBridge()
    turn_manager = TurnManager(
        config=build_config(tmp_path),
        session_store=store,
        recorder=recorder,
        stt=FakeSTT("refactor this repo"),
        tts=FakeTTS(),
        player=player,
        router=FakeRouter(RouteTarget.CODEX),
        planner=SpokenResponsePlanner(3, FakeVoiceShell()),
        voice_shell=FakeVoiceShell(),
        codex_bridge=codex,
        read_aloud=ReadAloudController(store, 6),
    )

    plan = await turn_manager.planner.plan("a very long response that should be summarized for speech", RouteTarget.CODEX)
    assert plan.mode == SpokenOutputMode.SUMMARY


@pytest.mark.asyncio
async def test_codex_route_plays_short_acknowledgement_while_waiting(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    recorder = FakeRecorder()
    player = FakePlayer()
    voice_shell = FakeVoiceShell()
    tts = FakeTTS()
    turn_manager = TurnManager(
        config=build_config(tmp_path),
        session_store=store,
        recorder=recorder,
        stt=FakeSTT("refactor this repo"),
        tts=tts,
        player=player,
        router=FakeRouter(RouteTarget.CODEX),
        planner=SpokenResponsePlanner(50, voice_shell),
        voice_shell=voice_shell,
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 6),
    )

    await turn_manager.ptt_down()
    await turn_manager.ptt_up()
    assert turn_manager._active_task is not None
    await turn_manager._active_task

    assert voice_shell.acks == ["refactor this repo"]
    assert tts.calls[0] == "Checking that."
    assert tts.calls[-1] == "codex response"


@pytest.mark.asyncio
async def test_mode_switch_transitions_to_listening_in_conversational_mode(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    turn_manager = TurnManager(
        config=build_config(tmp_path, mode=VoiceMode.CONVERSATIONAL),
        session_store=store,
        recorder=FakeRecorder(),
        stt=FakeSTT(),
        tts=FakeTTS(),
        player=FakePlayer(),
        router=FakeRouter(),
        planner=SpokenResponsePlanner(5, FakeVoiceShell()),
        voice_shell=FakeVoiceShell(),
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 6),
    )

    await turn_manager.set_mode(VoiceMode.CONVERSATIONAL)
    assert turn_manager.state == VoiceState.LISTENING


@pytest.mark.asyncio
async def test_read_file_uses_controller_chunk_and_tracks_response(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# Heading\n\nAlpha beta gamma delta.", encoding="utf-8")

    store = SessionStore(tmp_path / "sessions.sqlite3")
    player = FakePlayer()
    turn_manager = TurnManager(
        config=build_config(tmp_path),
        session_store=store,
        recorder=FakeRecorder(),
        stt=FakeSTT(),
        tts=FakeTTS(),
        player=player,
        router=FakeRouter(),
        planner=SpokenResponsePlanner(5, FakeVoiceShell()),
        voice_shell=FakeVoiceShell(),
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 6),
    )

    await turn_manager.read_file(source)
    assert turn_manager._active_task is not None
    await turn_manager._active_task

    assert turn_manager.last_response == "Heading\n\nAlpha beta gamma delta."
    assert player.played, "expected read-aloud playback to be invoked"


@pytest.mark.asyncio
async def test_read_aloud_controls_continue_repeat_skip_summarize_and_stop(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text(
        "# Heading\n\nAlpha beta gamma delta.\n\nEpsilon zeta eta theta.\n\nIota kappa lambda mu.",
        encoding="utf-8",
    )

    store = SessionStore(tmp_path / "sessions.sqlite3")
    player = FakePlayer()
    voice_shell = FakeVoiceShell()
    tts = FakeTTS()
    turn_manager = TurnManager(
        config=build_config(tmp_path),
        session_store=store,
        recorder=FakeRecorder(),
        stt=FakeSTT(),
        tts=tts,
        player=player,
        router=FakeRouter(),
        planner=SpokenResponsePlanner(5, voice_shell),
        voice_shell=voice_shell,
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 4),
    )

    await turn_manager.read_file(source)
    await turn_manager._active_task
    first_chunk = turn_manager.last_response

    await turn_manager.continue_reading()
    await turn_manager._active_task
    second_chunk = turn_manager.last_response

    await turn_manager.repeat_reading()
    await turn_manager._active_task
    repeated_chunk = turn_manager.last_response

    await turn_manager.skip_reading()
    await turn_manager._active_task
    third_chunk = turn_manager.last_response

    await turn_manager.summarize_reading()
    await turn_manager._active_task
    summary = turn_manager.last_response

    await turn_manager.stop_reading()

    assert first_chunk != second_chunk
    assert repeated_chunk == second_chunk
    assert third_chunk != second_chunk
    assert summary.startswith("summary:")
    assert turn_manager.read_aloud.document is None
    assert turn_manager.state == VoiceState.IDLE
    assert len(tts.calls) >= 4


@pytest.mark.asyncio
async def test_status_snapshot_includes_runtime_diagnostics(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    turn_manager = TurnManager(
        config=build_config(tmp_path),
        session_store=store,
        recorder=FakeRecorder(),
        stt=FakeSTT(),
        tts=FakeTTS(),
        player=FakePlayer(),
        router=FakeRouter(),
        planner=SpokenResponsePlanner(5, FakeVoiceShell()),
        voice_shell=FakeVoiceShell(),
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 6),
    )
    store.record_event(turn_manager.session_id, "PTT_DOWN", "RECORDING", {"from": "IDLE", "to": "RECORDING"})

    snapshot = await turn_manager.status_snapshot()

    assert snapshot.diagnostics["total_sessions"] == 1
    assert snapshot.diagnostics["total_events"] >= 1


@pytest.mark.asyncio
async def test_runtime_failure_recovers_to_ready_state(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    player = FakePlayer()
    turn_manager = TurnManager(
        config=build_config(tmp_path),
        session_store=store,
        recorder=FakeRecorder(),
        stt=FakeSTT("please help"),
        tts=FailingTTS(),
        player=player,
        router=FakeRouter(RouteTarget.LOCAL),
        planner=SpokenResponsePlanner(5, FakeVoiceShell()),
        voice_shell=FakeVoiceShell(),
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 6),
    )

    await turn_manager.ptt_down()
    await turn_manager.ptt_up()
    assert turn_manager._active_task is not None
    await turn_manager._active_task

    assert turn_manager.state == VoiceState.IDLE
    assert "tts_generation failed" in (turn_manager.last_response or "")
    events = store.recent_events(limit=5)
    assert any(event["event_type"] == VoiceEventType.FAIL.value for event in events)


@pytest.mark.asyncio
async def test_runtime_timeout_recovers_to_ready_state(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    player = FakePlayer()
    config = replace(build_config(tmp_path), stage_timeouts=StageTimeouts(transcription_seconds=0.01))
    turn_manager = TurnManager(
        config=config,
        session_store=store,
        recorder=FakeRecorder(),
        stt=SlowSTT("slow transcript"),
        tts=FakeTTS(),
        player=player,
        router=FakeRouter(RouteTarget.LOCAL),
        planner=SpokenResponsePlanner(5, FakeVoiceShell()),
        voice_shell=FakeVoiceShell(),
        codex_bridge=FakeCodexBridge(),
        read_aloud=ReadAloudController(store, 6),
    )

    await turn_manager.ptt_down()
    await turn_manager.ptt_up()
    assert turn_manager._active_task is not None
    await turn_manager._active_task

    assert turn_manager.state == VoiceState.IDLE
    assert turn_manager.last_response == "transcription timed out"
    events = store.recent_events(limit=5)
    assert any(event["event_type"] == VoiceEventType.TIMEOUT.value for event in events)
