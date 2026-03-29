from pathlib import Path

import pytest

from python_voicemode.realtime.config import RealtimeVoiceConfig
from python_voicemode.realtime.models import RouteTarget, StageTimeouts, VoiceMode, VoiceState
from python_voicemode.realtime.router import RouteClassifier


class DummyVoiceShell:
    async def route_hint(self, text: str):
        if "escalate" in text:
            return "codex"
        if "read" in text:
            return "read_aloud"
        return None


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
        summary_threshold_words=12,
        read_chunk_word_limit=6,
        prefer_mpv=False,
        auto_start_local_services=False,
        start_conversational_on_launch=False,
        pipecat_enabled=True,
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
async def test_route_classifier_prioritizes_read_commands():
    classifier = RouteClassifier(DummyVoiceShell())
    decision = await classifier.decide("continue reading", read_aloud_active=True)
    assert decision.target == RouteTarget.READ_ALOUD
    assert decision.command == "continue"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("utterance", "command"),
    [
        ("repeat last chunk", "repeat"),
        ("skip ahead", "skip"),
        ("summarize what you just read", "summarize"),
        ("stop reading", "stop"),
    ],
)
async def test_route_classifier_maps_read_control_commands(utterance, command):
    classifier = RouteClassifier(DummyVoiceShell())
    decision = await classifier.decide(utterance, read_aloud_active=True)
    assert decision.target == RouteTarget.READ_ALOUD
    assert decision.command == command


@pytest.mark.asyncio
async def test_route_classifier_sends_coding_requests_to_codex():
    classifier = RouteClassifier(DummyVoiceShell())
    decision = await classifier.decide("help me refactor this repo")
    assert decision.target == RouteTarget.CODEX


@pytest.mark.asyncio
async def test_route_classifier_uses_local_voice_shell_hint():
    classifier = RouteClassifier(DummyVoiceShell())
    decision = await classifier.decide("please escalate this")
    assert decision.target == RouteTarget.CODEX


@pytest.mark.asyncio
async def test_route_classifier_defaults_substantive_turns_to_codex():
    classifier = RouteClassifier(DummyVoiceShell())
    decision = await classifier.decide("what are the different modes this supports")
    assert decision.target == RouteTarget.CODEX


@pytest.mark.asyncio
async def test_route_classifier_keeps_brief_greetings_local():
    classifier = RouteClassifier(DummyVoiceShell())
    decision = await classifier.decide("hello")
    assert decision.target == RouteTarget.LOCAL


def test_conversation_modes_and_states_are_explicit():
    assert VoiceMode.WALKIE_TALKIE.value == "walkie-talkie"
    assert VoiceState.PLAYING_TTS.value == "PLAYING_TTS"
    assert VoiceState.INTERRUPTED.value == "INTERRUPTED"


def test_realtime_config_loads_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("VOICEMODE_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("VOICEMODE_RUNTIME_PORT", "8888")
    monkeypatch.setenv("VOICEMODE_RUNTIME_MODE", "conversational")
    monkeypatch.setenv("VOICEMODE_PTT_HOTKEY", "ctrl+space")
    monkeypatch.setenv("VOICEMODE_RUNTIME_MUTE", "true")
    monkeypatch.setenv("VOICEMODE_PIPECAT_ENABLED", "false")
    monkeypatch.setenv("VOICEMODE_VAD_BACKEND", "webrtc")
    monkeypatch.setenv("VOICEMODE_VAD_AGGRESSIVENESS", "3")
    monkeypatch.setenv("VOICEMODE_VAD_SILENCE_FRAMES", "9")
    config = RealtimeVoiceConfig.load(tmp_path)

    assert config.control_port == 8888
    assert config.mode == VoiceMode.CONVERSATIONAL
    assert config.ptt_hotkey == "ctrl+space"
    assert config.mute_voice_output is True
    assert config.pipecat_enabled is False
    assert config.vad_backend == "webrtc"
    assert config.vad_aggressiveness == 3
    assert config.vad_silence_frames == 9
    assert config.runtime_dir == tmp_path / "runtime"
