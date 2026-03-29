"""Startup checks and readiness reporting for the realtime runtime."""

from __future__ import annotations

import shutil

from .audio import MpvAudioPlayer
from .codex_bridge import CommandCodexBridge
from .config import RealtimeVoiceConfig
from .models import HealthStatus
from .pipecat_adapter import PipecatOrchestratorAdapter
from .stt import WhisperCppSTTAdapter
from .tts import KokoroTTSAdapter
from .vad import StreamingVad
from .voice_shell import OllamaVoiceShell


class VoiceStackLauncher:
    """Validate local dependencies and runtime readiness."""

    def __init__(
        self,
        config: RealtimeVoiceConfig,
        stt: WhisperCppSTTAdapter,
        tts: KokoroTTSAdapter,
        voice_shell: OllamaVoiceShell,
        codex: CommandCodexBridge,
        vad: StreamingVad,
        pipecat: PipecatOrchestratorAdapter,
    ):
        self.config = config
        self.stt = stt
        self.tts = tts
        self.voice_shell = voice_shell
        self.codex = codex
        self.vad = vad
        self.pipecat = pipecat

    async def health_report(self) -> list[HealthStatus]:
        mpv = MpvAudioPlayer()
        statuses = [
            HealthStatus("hammerspoon", shutil.which("hs") is not None, shutil.which("hs") or "not installed"),
            HealthStatus("mpv", mpv.is_available(), mpv.binary or "not installed"),
        ]
        vad_ok, vad_detail = self.vad.health()
        pipecat_ok, pipecat_detail = await self.pipecat.health()
        whisper_ok, whisper_detail = await self.stt.health()
        kokoro_ok, kokoro_detail = await self.tts.health()
        ollama_ok, ollama_detail = await self.voice_shell.health()
        codex_ok, codex_detail = await self.codex.health()
        statuses.extend(
            [
                HealthStatus("vad", vad_ok, vad_detail),
                HealthStatus("pipecat", pipecat_ok, pipecat_detail),
                HealthStatus("whisper.cpp", whisper_ok, whisper_detail),
                HealthStatus("kokoro", kokoro_ok, kokoro_detail),
                HealthStatus("ollama", ollama_ok, ollama_detail),
                HealthStatus("codex", codex_ok, codex_detail),
            ]
        )
        return statuses

    async def readiness_text(self) -> str:
        lines = [
            "Voice runtime readiness",
            "=======================",
            f"Control URL: {self.config.control_base_url}",
            f"Default mode: {self.config.mode.value}",
        ]
        for status in await self.health_report():
            icon = "OK" if status.ok else "FAIL"
            lines.append(f"{icon:<4} {status.name:<12} {status.detail}")
        return "\n".join(lines)
