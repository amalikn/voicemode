"""Runtime server exposing local control endpoints for the voice stack."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import tempfile
from pathlib import Path

import numpy as np
from aiohttp import web

from .audio import MpvAudioPlayer, NullAudioPlayer
from .codex_bridge import CommandCodexBridge
from .config import RealtimeVoiceConfig
from .launcher import VoiceStackLauncher
from .microphone import OpenMicStream, PushToTalkRecorder, write_wav
from .models import VoiceEventType, VoiceMode
from .pipecat_adapter import PipecatOrchestratorAdapter
from .ptt import write_hammerspoon_config
from .read_aloud import ReadAloudController
from .router import RouteClassifier
from .session_store import SessionStore
from .stt import WhisperCppSTTAdapter
from .summary import SpokenResponsePlanner
from .tts import KokoroTTSAdapter
from .turn_manager import TurnManager
from .vad import StreamingVad
from .voice_shell import OllamaVoiceShell

logger = logging.getLogger("voicemode.realtime.orchestrator")


class VoiceRuntimeServer:
    """Own the long-running voice daemon and local control API."""

    def __init__(self, config: RealtimeVoiceConfig):
        self.config = config
        self.config.ensure_directories()
        self.session_store = SessionStore(config.session_db_path)
        self.voice_shell = OllamaVoiceShell(config.ollama_base_url, config.ollama_model)
        self.codex_bridge = CommandCodexBridge(config.codex_command, config.workspace_dir)
        self.pipecat = PipecatOrchestratorAdapter(config.pipecat_enabled)
        self.stt = WhisperCppSTTAdapter(config.stt_base_url)
        self.tts = KokoroTTSAdapter(config.tts_base_url, config.kokoro_model, config.kokoro_voice)
        player = MpvAudioPlayer() if config.prefer_mpv else NullAudioPlayer()
        if not player.is_available():
            player = NullAudioPlayer()
        self.turn_manager = TurnManager(
            config=config,
            session_store=self.session_store,
            recorder=PushToTalkRecorder(),
            stt=self.stt,
            tts=self.tts,
            player=player,
            router=RouteClassifier(self.voice_shell),
            planner=SpokenResponsePlanner(config.summary_threshold_words, self.voice_shell),
            voice_shell=self.voice_shell,
            codex_bridge=self.codex_bridge,
            read_aloud=ReadAloudController(self.session_store, config.read_chunk_word_limit),
        )
        self.vad = StreamingVad(
            config.vad_energy_threshold,
            silence_frames=config.vad_silence_frames,
            backend=config.vad_backend,
            aggressiveness=config.vad_aggressiveness,
        )
        self.launcher = VoiceStackLauncher(
            config,
            self.stt,
            self.tts,
            self.voice_shell,
            self.codex_bridge,
            self.vad,
            self.pipecat,
        )
        self.app = web.Application()
        self.app.add_routes(
            [
                web.get("/status", self.handle_status),
                web.get("/diag", self.handle_diag),
                web.post("/control", self.handle_control),
                web.post("/read-file", self.handle_read_file),
                web.post("/hammerspoon/export", self.handle_export_hammerspoon),
            ]
        )
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self.stop_event = asyncio.Event()
        self.open_mic: OpenMicStream | None = None
        self.conversation_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.config.control_host, self.config.control_port)
        await self.site.start()
        if self.config.start_conversational_on_launch:
            await self.enable_conversational_mode()

    async def run_forever(self) -> None:
        await self.start()
        try:
            await self.stop_event.wait()
        finally:
            await self.stop()

    async def stop(self) -> None:
        if self.conversation_task is not None:
            self.conversation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.conversation_task
            self.conversation_task = None
        if self.open_mic is not None:
            await self.open_mic.stop()
            self.open_mic = None
        await self.vad.aclose()
        await self.turn_manager.close()
        if self.runner is not None:
            await self.runner.cleanup()

    async def enable_conversational_mode(self) -> None:
        await self.turn_manager.set_mode(VoiceMode.CONVERSATIONAL)
        if self.open_mic is None:
            self.open_mic = OpenMicStream()
            await self.open_mic.start()
            self.conversation_task = asyncio.create_task(self._conversation_loop())

    async def disable_conversational_mode(self) -> None:
        await self.turn_manager.set_mode(VoiceMode.WALKIE_TALKIE)
        if self.conversation_task is not None:
            self.conversation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.conversation_task
            self.conversation_task = None
        if self.open_mic is not None:
            await self.open_mic.stop()
            self.open_mic = None

    async def _conversation_loop(self) -> None:
        assert self.open_mic is not None
        buffer: list[np.ndarray] = []
        while True:
            frame = await self.open_mic.read_frame()
            transition = await self.vad.process_frame(frame)
            if transition.speech_started:
                self.session_store.record_event(
                    self.turn_manager.session_id,
                    VoiceEventType.VAD_SPEECH_START.value,
                    self.turn_manager.state.value,
                    {},
                )
                await self.turn_manager.stop_speaking()
                buffer = [frame]
                continue
            if transition.speech_active:
                buffer.append(frame)
                continue
            if transition.speech_ended and buffer:
                self.session_store.record_event(
                    self.turn_manager.session_id,
                    VoiceEventType.VAD_SPEECH_END.value,
                    self.turn_manager.state.value,
                    {},
                )
                samples = np.concatenate(buffer, axis=0).reshape(-1)
                with tempfile.NamedTemporaryFile(
                    suffix=".wav",
                    prefix="vad-",
                    dir=self.config.recordings_dir,
                    delete=False,
                ) as handle:
                    path = write_wav(Path(handle.name), samples, self.open_mic.sample_rate)
                await self.turn_manager.process_vad_audio(path)
                buffer = []

    async def handle_status(self, _request: web.Request) -> web.Response:
        health = await self.launcher.health_report()
        snapshot = await self.turn_manager.status_snapshot(health=health)
        return web.json_response(
            {
                "mode": snapshot.mode.value,
                "state": snapshot.state.value,
                "muted": snapshot.muted,
                "session_id": snapshot.current_session_id,
                "last_transcript": snapshot.last_transcript,
                "last_response": snapshot.last_response,
                "reading_document": snapshot.reading_document,
                "reading_cursor": snapshot.reading_cursor,
                "diagnostics": snapshot.diagnostics,
            }
        )

    async def handle_diag(self, _request: web.Request) -> web.Response:
        snapshot = await self.turn_manager.status_snapshot(health=await self.launcher.health_report())
        return web.json_response(
            {
                "mode": snapshot.mode.value,
                "state": snapshot.state.value,
                "last_20_events": snapshot.last_events,
                "diagnostics": snapshot.diagnostics,
                "health": [
                    {"name": item.name, "ok": item.ok, "detail": item.detail}
                    for item in snapshot.health
                ],
            }
        )

    async def handle_read_file(self, request: web.Request) -> web.Response:
        payload = await request.json()
        path = Path(payload["path"]).expanduser()
        await self.turn_manager.read_file(path)
        return web.json_response({"accepted": True, "path": str(path)})

    async def handle_export_hammerspoon(self, request: web.Request) -> web.Response:
        payload = await request.json()
        output_path = Path(payload["path"]).expanduser()
        write_hammerspoon_config(self.config, output_path)
        return web.json_response({"written": str(output_path)})

    async def handle_control(self, request: web.Request) -> web.Response:
        payload = await request.json()
        event = payload.get("event")
        if event == VoiceEventType.PTT_DOWN.value:
            await self.turn_manager.ptt_down()
        elif event == VoiceEventType.PTT_UP.value:
            await self.turn_manager.ptt_up()
        elif event == VoiceEventType.TTS_STOP.value:
            await self.turn_manager.stop_speaking()
        elif event == VoiceEventType.READ_CONTINUE.value:
            await self.turn_manager.continue_reading()
        elif event == VoiceEventType.READ_REPEAT.value:
            await self.turn_manager.repeat_reading()
        elif event == VoiceEventType.READ_SKIP.value:
            await self.turn_manager.skip_reading()
        elif event == VoiceEventType.READ_SUMMARIZE.value:
            await self.turn_manager.summarize_reading()
        elif event == VoiceEventType.READ_STOP.value:
            await self.turn_manager.stop_reading()
        elif event == VoiceEventType.MODE_SWITCH.value:
            mode = VoiceMode(payload["mode"])
            if mode == VoiceMode.CONVERSATIONAL:
                await self.enable_conversational_mode()
            else:
                await self.disable_conversational_mode()
        else:
            return web.json_response({"accepted": False, "error": f"unknown event {event}"}, status=400)
        return web.json_response({"accepted": True, "event": event})
