"""Explicit turn ownership and cancel-and-replace orchestration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path

from python_voicemode.utils import get_event_logger

from .audio import AudioPlayer
from .config import RealtimeVoiceConfig
from .models import RouteTarget, RuntimeSnapshot, SpokenOutputMode, VoiceEventType, VoiceMode, VoiceState
from .read_aloud import ReadAloudController
from .router import RouteClassifier
from .session_store import SessionStore
from .summary import SpokenResponsePlanner

logger = logging.getLogger("voicemode.realtime.turn_manager")


class StageTimeoutError(asyncio.TimeoutError):
    """Attach stage context to timeouts."""

    def __init__(self, stage: str):
        super().__init__(stage)
        self.stage = stage


class StageExecutionError(RuntimeError):
    """Attach stage context to runtime failures."""

    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


class TurnManager:
    """Coordinate capture, routing, response generation, and playback."""

    def __init__(
        self,
        config: RealtimeVoiceConfig,
        session_store: SessionStore,
        recorder,
        stt,
        tts,
        player: AudioPlayer,
        router: RouteClassifier,
        planner: SpokenResponsePlanner,
        voice_shell,
        codex_bridge,
        read_aloud: ReadAloudController,
    ):
        self.config = config
        self.session_store = session_store
        self.recorder = recorder
        self.stt = stt
        self.tts = tts
        self.player = player
        self.router = router
        self.planner = planner
        self.voice_shell = voice_shell
        self.codex_bridge = codex_bridge
        self.read_aloud = read_aloud
        self.mode = config.mode
        self.state = VoiceState.IDLE
        self.muted = config.mute_voice_output
        self.session_id = session_store.create_session(self.mode.value, {"workspace": str(config.workspace_dir)})
        self._state_lock = asyncio.Lock()
        self._active_task: asyncio.Task | None = None
        self.last_transcript: str | None = None
        self.last_response: str | None = None

    async def close(self) -> None:
        await self._cancel_active_task("shutdown")
        await self.player.stop()
        self.session_store.close_session(self.session_id)

    async def set_mode(self, mode: VoiceMode) -> None:
        self.mode = mode
        target = VoiceState.LISTENING if mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE
        await self._transition(target, VoiceEventType.MODE_SWITCH, {"mode": mode.value})

    async def ptt_down(self) -> None:
        await self._barge_in("ptt_down")
        self.recorder.start()
        await self._transition(VoiceState.RECORDING, VoiceEventType.PTT_DOWN, {})

    async def ptt_up(self) -> None:
        if not self.recorder.active:
            return
        timestamp = int(time.time() * 1000)
        path = self.config.recordings_dir / f"ptt-{timestamp}.wav"
        audio_path = await asyncio.to_thread(self.recorder.stop, path)
        await self._launch_processing(audio_path, VoiceEventType.PTT_UP)

    async def process_vad_audio(self, audio_path: Path) -> None:
        await self._launch_processing(audio_path, VoiceEventType.VAD_SPEECH_END)

    async def read_file(self, path: Path) -> None:
        self.read_aloud.load_file(path)
        self.last_response = self.read_aloud.current_chunk()
        await self._start_task(self._play_reading(event=VoiceEventType.ROUTE_READ_ALOUD), stage="read_aloud")

    async def continue_reading(self) -> None:
        await self._start_task(self._play_reading(event=VoiceEventType.READ_CONTINUE, advance=True), stage="read_aloud")

    async def repeat_reading(self) -> None:
        chunk = self.read_aloud.repeat_last()
        if chunk is None:
            self.last_response = "Nothing is currently active for read-aloud."
            return
        self.last_response = chunk
        await self._start_task(
            self._speak_text(chunk, VoiceState.READING_CHUNK, VoiceEventType.READ_REPEAT),
            stage="read_aloud",
        )

    async def skip_reading(self) -> None:
        chunk = self.read_aloud.skip_next_section()
        if chunk is None:
            self.last_response = "No next section is available."
            return
        self.last_response = chunk
        await self._start_task(
            self._speak_text(chunk, VoiceState.READING_CHUNK, VoiceEventType.READ_SKIP),
            stage="read_aloud",
        )

    async def summarize_reading(self) -> None:
        summary = self.read_aloud.summarize_context()
        if self.voice_shell is not None:
            refined = await self.voice_shell.summarize_for_speech(summary)
            if refined:
                summary = refined
        self.last_response = summary
        await self._start_task(
            self._speak_text(summary, VoiceState.PLAYING_TTS, VoiceEventType.READ_SUMMARIZE),
            stage="read_aloud",
        )

    async def stop_reading(self) -> None:
        self.read_aloud.stop()
        await self.stop_speaking()

    async def stop_speaking(self) -> None:
        await self._barge_in("stop_speaking")
        target = VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE
        await self._transition(target, VoiceEventType.TTS_STOP, {})

    async def status_snapshot(self, health=None) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            mode=self.mode,
            state=self.state,
            muted=self.muted,
            current_session_id=self.session_id,
            last_transcript=self.last_transcript,
            last_response=self.last_response,
            reading_document=self.read_aloud.document.title if self.read_aloud.document else None,
            reading_cursor=self.read_aloud.document.cursor if self.read_aloud.document else 0,
            last_events=self.session_store.recent_events(),
            health=health or [],
            diagnostics=self.session_store.diagnostics_summary(),
        )

    async def _launch_processing(self, audio_path: Path, trigger_event: VoiceEventType) -> None:
        await self._start_task(self._process_audio(audio_path, trigger_event), stage="transcription_pipeline")

    async def _process_audio(self, audio_path: Path, trigger_event: VoiceEventType) -> None:
        await self._transition(VoiceState.TRANSCRIBING, trigger_event, {"audio_path": str(audio_path)})
        transcript = await self._await_stage(
            self.stt.transcribe_file(audio_path),
            timeout=self.config.stage_timeouts.transcription_seconds,
            stage="transcription",
        )
        self.last_transcript = transcript
        await self._record(VoiceEventType.TRANSCRIPT_READY, {"text": transcript})
        if not transcript:
            target = VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE
            await self._transition(target, VoiceEventType.TRANSCRIPT_READY, {"empty": True})
            return

        await self._transition(VoiceState.ROUTING, VoiceEventType.TRANSCRIPT_READY, {"text": transcript})
        route = await self._await_stage(
            self.router.decide(transcript, read_aloud_active=self.read_aloud.is_active),
            timeout=self.config.stage_timeouts.routing_seconds,
            stage="routing",
        )
        if route.target == RouteTarget.READ_ALOUD:
            await self._handle_read_route(transcript, route.command)
            return
        if route.target == RouteTarget.CODEX:
            await self._transition(VoiceState.WAITING_CODEX, VoiceEventType.ROUTE_CODEX, {"reason": route.reason})
            codex_task = asyncio.create_task(
                self.codex_bridge.answer(
                    transcript,
                    timeout=self.config.stage_timeouts.codex_seconds,
                )
            )
            try:
                await self._acknowledge_codex_wait(transcript)
                response_text = await self._await_stage(
                    codex_task,
                    timeout=self.config.stage_timeouts.codex_seconds,
                    stage="codex",
                )
            finally:
                if not codex_task.done():
                    codex_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await codex_task
        else:
            await self._transition(VoiceState.WAITING_LOCAL, VoiceEventType.ROUTE_LOCAL, {"reason": route.reason})
            response_text = await self._await_stage(
                self.voice_shell.answer_short(transcript),
                timeout=self.config.stage_timeouts.local_llm_seconds,
                stage="local_llm",
            )
        self.last_response = response_text
        plan = await self.planner.plan(
            response_text,
            route.target,
            read_aloud=False,
            voice_enabled=not self.muted,
        )
        if not plan.should_speak:
            target = VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE
            await self._transition(target, VoiceEventType.TTS_STOP, {"muted": True})
            return
        await self._play_plan(plan)

    async def _handle_read_route(self, transcript: str, command: str | None) -> None:
        normalized = transcript.lower()
        if command == "stop":
            await self.stop_reading()
            return
        if command == "continue":
            chunk = self.read_aloud.advance() if self.read_aloud.is_active else None
            if chunk is None:
                self.last_response = "Nothing is ready to continue."
                return
            await self._start_task(
                self._speak_text(chunk, VoiceState.READING_CHUNK, VoiceEventType.READ_CONTINUE),
                stage="read_aloud",
            )
            return
        if command == "repeat":
            await self.repeat_reading()
            return
        if command == "skip":
            await self.skip_reading()
            return
        if command == "summarize":
            await self.summarize_reading()
            return
        path = self._resolve_path_from_transcript(transcript)
        if path is None:
            self.last_response = "Read-aloud needs a file path or an active reading session."
            target = VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE
            await self._transition(target, VoiceEventType.FAIL, {"reason": "missing read target"})
            return
        await self.read_file(path)

    def _resolve_path_from_transcript(self, transcript: str) -> Path | None:
        normalized = transcript.strip()
        for token in normalized.split():
            candidate = Path(token).expanduser()
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    async def _play_reading(self, event: VoiceEventType, advance: bool = True) -> None:
        chunk = self.read_aloud.current_chunk()
        if chunk is None:
            self.last_response = "Nothing is queued for read-aloud."
            target = VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE
            await self._transition(target, VoiceEventType.FAIL, {"reason": "no active read session"})
            return
        if advance and event == VoiceEventType.READ_CONTINUE:
            next_chunk = self.read_aloud.advance()
            if next_chunk is None:
                self.last_response = "Reached the end of the document."
                target = VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE
                await self._transition(target, VoiceEventType.READ_STOP, {"reason": "end_of_document"})
                return
            chunk = next_chunk
        self.last_response = chunk
        await self._speak_text(chunk, VoiceState.READING_CHUNK, event)

    async def _play_plan(self, plan) -> None:
        if plan.mode == SpokenOutputMode.CHUNKED and plan.chunks:
            for chunk in plan.chunks:
                await self._speak_text(chunk, VoiceState.READING_CHUNK, VoiceEventType.TTS_START)
            return
        await self._speak_text(plan.spoken_text, VoiceState.PLAYING_TTS, VoiceEventType.TTS_START)

    async def _acknowledge_codex_wait(self, transcript: str) -> None:
        if self.voice_shell is None:
            return
        if self.muted or not self.player.is_available():
            return
        try:
            acknowledgement = await self._await_stage(
                self.voice_shell.acknowledge(transcript),
                timeout=min(2.0, self.config.stage_timeouts.local_llm_seconds),
                stage="codex_ack",
            )
        except Exception:
            return
        if not acknowledgement:
            return
        await self._speak_text(
            acknowledgement,
            VoiceState.WAITING_CODEX,
            VoiceEventType.TTS_START,
            resume_state=VoiceState.WAITING_CODEX,
        )

    async def _speak_text(
        self,
        text: str,
        state: VoiceState,
        event: VoiceEventType,
        resume_state: VoiceState | None = None,
    ) -> None:
        if self.muted:
            target = resume_state or (VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE)
            await self._transition(target, VoiceEventType.TTS_STOP, {"muted": True})
            return
        if not self.player.is_available():
            self.muted = True
            target = resume_state or (VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE)
            await self._transition(target, VoiceEventType.FAIL, {"reason": "audio player unavailable"})
            return
        timestamp = int(time.time() * 1000)
        audio_path = self.config.tts_dir / f"tts-{timestamp}.mp3"
        await self._transition(state, event, {"spoken_text": text[:200]})
        await self._await_stage(
            self.tts.synthesize_to_file(text, audio_path),
            timeout=self.config.stage_timeouts.tts_generation_seconds,
            stage="tts_generation",
        )
        await self.player.play(audio_path)
        await self._await_stage(
            self.player.wait(timeout=self.config.stage_timeouts.playback_seconds),
            timeout=self.config.stage_timeouts.playback_seconds,
            stage="playback",
        )
        target = resume_state or (VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE)
        await self._transition(target, VoiceEventType.TTS_STOP, {})

    async def _barge_in(self, reason: str) -> None:
        await self.player.stop()
        await self._cancel_active_task(reason)
        await self._transition(VoiceState.INTERRUPTED, VoiceEventType.BARGE_IN, {"reason": reason})

    async def _start_task(self, coro, stage: str) -> None:
        current = asyncio.current_task()
        if current is not None and current is self._active_task:
            await coro
            return
        try:
            await self._cancel_active_task("replace_active_task")
            self._active_task = asyncio.create_task(self._run_task(coro, stage=stage))
        except BaseException:
            coro.close()
            raise

    async def _run_task(self, coro, stage: str) -> None:
        try:
            await coro
        except StageTimeoutError as exc:
            await self._handle_runtime_failure(VoiceEventType.TIMEOUT, exc.stage, f"{exc.stage} timed out")
        except StageExecutionError as exc:
            await self._handle_runtime_failure(VoiceEventType.FAIL, exc.stage, str(exc))
        except asyncio.TimeoutError:
            await self._handle_runtime_failure(VoiceEventType.TIMEOUT, stage, f"{stage} timed out")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("runtime task failed", extra={"stage": stage})
            await self._handle_runtime_failure(VoiceEventType.FAIL, stage, f"{stage} failed: {exc}")

    async def _await_stage(self, coro, timeout: float, stage: str):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise StageTimeoutError(stage) from exc
        except StageTimeoutError:
            raise
        except Exception as exc:
            raise StageExecutionError(stage, f"{stage} failed: {exc}") from exc

    async def _handle_runtime_failure(self, event: VoiceEventType, stage: str, message: str) -> None:
        self.last_response = message
        await self.player.stop()
        await self._transition(VoiceState.ERROR, event, {"stage": stage, "message": message})
        target = VoiceState.LISTENING if self.mode == VoiceMode.CONVERSATIONAL else VoiceState.IDLE
        await self._transition(target, event, {"stage": stage, "recovered": True})

    async def _cancel_active_task(self, reason: str) -> None:
        if self._active_task is None:
            return
        if self._active_task.done():
            self._active_task = None
            return
        self._active_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._active_task
        await self._record(VoiceEventType.BARGE_IN, {"cancelled_reason": reason})
        self._active_task = None

    async def _transition(self, new_state: VoiceState, event: VoiceEventType, details: dict) -> None:
        async with self._state_lock:
            previous = self.state
            self.state = new_state
            payload = {"from": previous.value, "to": new_state.value, **details}
            self.session_store.record_event(self.session_id, event.value, new_state.value, payload)
            event_logger = get_event_logger()
            if event_logger:
                event_logger.log_event(
                    VoiceEventType.STATE_TRANSITION.value,
                    {"event": event.value, **payload},
                )
            logger.info(
                "state transition",
                extra={"event": event.value, "details": payload},
            )

    async def _record(self, event: VoiceEventType, details: dict) -> None:
        self.session_store.record_event(self.session_id, event.value, self.state.value, details)
