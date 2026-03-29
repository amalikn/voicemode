"""Configuration for the realtime voice runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from python_voicemode.config import BASE_DIR, KOKORO_PORT, TTS_BASE_URLS, STT_BASE_URLS, WHISPER_PORT

from .models import StageTimeouts, VoiceMode


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RealtimeVoiceConfig:
    """Runtime configuration loaded from environment variables."""

    workspace_dir: Path
    runtime_dir: Path
    logs_dir: Path
    recordings_dir: Path
    tts_dir: Path
    session_db_path: Path
    control_host: str
    control_port: int
    mode: VoiceMode
    ptt_hotkey: str
    mute_voice_output: bool
    summary_threshold_words: int
    read_chunk_word_limit: int
    prefer_mpv: bool
    auto_start_local_services: bool
    start_conversational_on_launch: bool
    pipecat_enabled: bool
    tts_base_url: str
    stt_base_url: str
    ollama_base_url: str
    ollama_model: str
    kokoro_model: str
    kokoro_voice: str
    codex_command: str
    vad_backend: str
    vad_aggressiveness: int
    vad_silence_frames: int
    vad_energy_threshold: float
    stage_timeouts: StageTimeouts

    @property
    def control_base_url(self) -> str:
        return f"http://{self.control_host}:{self.control_port}"

    @classmethod
    def load(cls, workspace_dir: Path | None = None) -> "RealtimeVoiceConfig":
        workspace = workspace_dir or Path.cwd()
        runtime_dir = Path(os.getenv("VOICEMODE_RUNTIME_DIR", str(BASE_DIR / "realtime")))
        logs_dir = Path(os.getenv("VOICEMODE_RUNTIME_LOG_DIR", str(runtime_dir / "logs")))
        recordings_dir = runtime_dir / "recordings"
        tts_dir = runtime_dir / "tts"
        session_db_path = Path(
            os.getenv("VOICEMODE_RUNTIME_DB", str(runtime_dir / "sessions.sqlite3"))
        )
        mode_raw = os.getenv("VOICEMODE_RUNTIME_MODE", VoiceMode.WALKIE_TALKIE.value)
        try:
            mode = VoiceMode(mode_raw)
        except ValueError:
            mode = VoiceMode.WALKIE_TALKIE
        return cls(
            workspace_dir=workspace,
            runtime_dir=runtime_dir,
            logs_dir=logs_dir,
            recordings_dir=recordings_dir,
            tts_dir=tts_dir,
            session_db_path=session_db_path,
            control_host=os.getenv("VOICEMODE_RUNTIME_HOST", "127.0.0.1"),
            control_port=int(os.getenv("VOICEMODE_RUNTIME_PORT", "8766")),
            mode=mode,
            ptt_hotkey=os.getenv("VOICEMODE_PTT_HOTKEY", "cmd+shift+space"),
            mute_voice_output=_env_bool("VOICEMODE_RUNTIME_MUTE", False),
            summary_threshold_words=int(os.getenv("VOICEMODE_SUMMARY_THRESHOLD_WORDS", "120")),
            read_chunk_word_limit=int(os.getenv("VOICEMODE_READ_CHUNK_WORD_LIMIT", "90")),
            prefer_mpv=_env_bool("VOICEMODE_PREFER_MPV", True),
            auto_start_local_services=_env_bool("VOICEMODE_RUNTIME_AUTO_START_SERVICES", False),
            start_conversational_on_launch=_env_bool(
                "VOICEMODE_RUNTIME_START_CONVERSATIONAL",
                mode == VoiceMode.CONVERSATIONAL,
            ),
            pipecat_enabled=_env_bool("VOICEMODE_PIPECAT_ENABLED", True),
            tts_base_url=os.getenv(
                "VOICEMODE_RUNTIME_TTS_BASE_URL",
                TTS_BASE_URLS[0] if TTS_BASE_URLS else f"http://127.0.0.1:{KOKORO_PORT}/v1",
            ),
            stt_base_url=os.getenv(
                "VOICEMODE_RUNTIME_STT_BASE_URL",
                STT_BASE_URLS[0] if STT_BASE_URLS else f"http://127.0.0.1:{WHISPER_PORT}/v1",
            ),
            ollama_base_url=os.getenv("VOICEMODE_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("VOICEMODE_OLLAMA_MODEL", "phi4-mini"),
            kokoro_model=os.getenv("VOICEMODE_RUNTIME_TTS_MODEL", "tts-1"),
            kokoro_voice=os.getenv("VOICEMODE_RUNTIME_TTS_VOICE", "af_sky"),
            codex_command=os.getenv(
                "VOICEMODE_CODEX_COMMAND",
                "codex exec --json --skip-git-repo-check -C {workspace}",
            ),
            vad_backend=os.getenv("VOICEMODE_VAD_BACKEND", "auto").strip().lower() or "auto",
            vad_aggressiveness=int(os.getenv("VOICEMODE_VAD_AGGRESSIVENESS", "2")),
            vad_silence_frames=int(os.getenv("VOICEMODE_VAD_SILENCE_FRAMES", "15")),
            vad_energy_threshold=float(os.getenv("VOICEMODE_VAD_ENERGY_THRESHOLD", "0.012")),
            stage_timeouts=StageTimeouts(
                recording_seconds=float(os.getenv("VOICEMODE_TIMEOUT_RECORDING", "30")),
                transcription_seconds=float(os.getenv("VOICEMODE_TIMEOUT_STT", "20")),
                routing_seconds=float(os.getenv("VOICEMODE_TIMEOUT_ROUTING", "4")),
                local_llm_seconds=float(os.getenv("VOICEMODE_TIMEOUT_LOCAL_LLM", "8")),
                codex_seconds=float(os.getenv("VOICEMODE_TIMEOUT_CODEX", "120")),
                tts_generation_seconds=float(os.getenv("VOICEMODE_TIMEOUT_TTS_GENERATION", "20")),
                playback_seconds=float(os.getenv("VOICEMODE_TIMEOUT_PLAYBACK", "90")),
            ),
        )

    def ensure_directories(self) -> None:
        """Create runtime directories."""
        for path in (self.runtime_dir, self.logs_dir, self.recordings_dir, self.tts_dir):
            path.mkdir(parents=True, exist_ok=True)
