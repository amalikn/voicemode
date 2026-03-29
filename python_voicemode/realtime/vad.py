"""Streaming VAD helpers for conversational mode."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np

try:
    import webrtcvad
except ImportError:  # pragma: no cover - optional dependency
    webrtcvad = None

try:  # pragma: no cover - optional dependency surface
    from livekit import rtc
    from livekit.agents.vad import VADEventType
    from livekit.agents.utils.aio.channel import ChanEmpty
    from livekit.plugins import silero as livekit_silero
except ImportError:  # pragma: no cover - optional dependency
    rtc = None
    ChanEmpty = Exception  # type: ignore[assignment]
    VADEventType = None
    livekit_silero = None


@dataclass
class VadTransition:
    speech_started: bool = False
    speech_ended: bool = False
    speech_active: bool = False


class StreamingVad:
    """Streaming VAD with backend selection and stable fallbacks.

    Backend order:
    - `silero` when explicitly requested and available
    - `webrtc` when explicitly requested and available
    - `auto` prefers Silero, then WebRTC, then energy fallback
    - `energy` is the last-resort stable fallback
    """

    def __init__(
        self,
        energy_threshold: float,
        silence_frames: int = 15,
        backend: str = "auto",
        aggressiveness: int = 2,
        sample_rate: int = 16_000,
        frame_duration_ms: int = 30,
    ):
        self.energy_threshold = energy_threshold
        self.silence_frames = silence_frames
        self.requested_backend = backend.strip().lower() or "auto"
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.speaking = False
        self.trailing_silence = 0
        self._aggressiveness = max(0, min(3, aggressiveness))
        self._pcm_remainder = np.empty(0, dtype=np.int16)
        self._frame_samples = max(int(self.sample_rate * self.frame_duration_ms / 1000), 1)
        self._webrtc_vad = None
        self._silero_vad = None
        self._silero_stream = None
        self.backend_name = "energy"
        self.backend_detail = "energy gate fallback"
        self._select_backend()

    def _select_backend(self) -> None:
        requested = self.requested_backend
        if requested not in {"auto", "silero", "webrtc", "energy"}:
            requested = "auto"

        if requested in {"auto", "silero"} and livekit_silero is not None and rtc is not None and VADEventType is not None:
            self.backend_name = "silero"
            self.backend_detail = "silero selected (lazy load)"
            return

        if requested in {"auto", "webrtc"} and webrtcvad is not None:
            self._webrtc_vad = webrtcvad.Vad(self._aggressiveness)
            self.backend_name = "webrtc"
            self.backend_detail = f"webrtcvad aggressiveness={self._aggressiveness}"
            return

        if requested == "silero":
            self.backend_detail = "silero unavailable, using energy fallback"
        elif requested == "webrtc":
            self.backend_detail = "webrtcvad unavailable, using energy fallback"

    def health(self) -> tuple[bool, str]:
        return True, f"{self.backend_name}: {self.backend_detail}"

    async def process_frame(self, frame: np.ndarray) -> VadTransition:
        if self.backend_name == "silero":
            return await self._process_frame_silero(frame)
        if self.backend_name == "webrtc":
            return self._transition_for(self._detect_speech_webrtc(frame))
        return self._transition_for(self._detect_speech_energy(frame))

    async def aclose(self) -> None:
        if self._silero_stream is not None:
            await self._silero_stream.aclose()
            self._silero_stream = None

    def _transition_for(self, speech: bool) -> VadTransition:
        transition = VadTransition(speech_active=speech or self.speaking)
        if speech:
            self.trailing_silence = 0
            if not self.speaking:
                self.speaking = True
                transition.speech_started = True
        elif self.speaking:
            self.trailing_silence += 1
            if self.trailing_silence >= self.silence_frames:
                self.speaking = False
                self.trailing_silence = 0
                transition.speech_ended = True
                transition.speech_active = False
        return transition

    def _detect_speech_energy(self, frame: np.ndarray) -> bool:
        energy = float(np.abs(frame).mean()) if frame.size else 0.0
        return energy >= self.energy_threshold

    def _detect_speech_webrtc(self, frame: np.ndarray) -> bool:
        if self._webrtc_vad is None or frame.size == 0:
            return False

        int16_frame = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
        buffer = np.concatenate((self._pcm_remainder, int16_frame))
        speech_detected = False
        consumed = 0

        while buffer.size - consumed >= self._frame_samples:
            chunk = buffer[consumed : consumed + self._frame_samples]
            try:
                if self._webrtc_vad.is_speech(chunk.tobytes(), self.sample_rate):
                    speech_detected = True
            except Exception:
                self._demote_to_energy("webrtcvad failed at runtime, using energy fallback")
                return self._detect_speech_energy(frame)
            consumed += self._frame_samples

        self._pcm_remainder = buffer[consumed:]
        if consumed == 0:
            return self._detect_speech_energy(frame)
        return speech_detected

    async def _process_frame_silero(self, frame: np.ndarray) -> VadTransition:
        stream = await self._ensure_silero_stream()
        if stream is None or rtc is None or VADEventType is None:
            return self._transition_for(self._detect_speech_energy(frame))

        int16_frame = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
        audio_frame = rtc.AudioFrame(
            data=int16_frame.tobytes(),
            sample_rate=self.sample_rate,
            num_channels=1,
            samples_per_channel=int16_frame.size,
        )
        stream.push_frame(audio_frame)
        await asyncio.sleep(0)

        transition = VadTransition(speech_active=self.speaking)
        while True:
            try:
                event = stream._event_ch.recv_nowait()
            except ChanEmpty:
                break

            if event.type == VADEventType.START_OF_SPEECH:
                self.speaking = True
                transition.speech_started = True
                transition.speech_active = True
            elif event.type == VADEventType.END_OF_SPEECH:
                self.speaking = False
                transition.speech_ended = True
                transition.speech_active = False
            else:
                transition.speech_active = self.speaking
        return transition

    async def _ensure_silero_stream(self):
        if self._silero_stream is not None:
            return self._silero_stream
        if livekit_silero is None:
            self._demote_to_webrtc_or_energy("silero unavailable, using fallback")
            return None
        try:
            if self._silero_vad is None:
                self._silero_vad = await asyncio.to_thread(
                    livekit_silero.VAD.load,
                    sample_rate=self.sample_rate,
                    force_cpu=True,
                )
            self._silero_stream = self._silero_vad.stream()
            self.backend_name = "silero"
            self.backend_detail = "silero active"
            return self._silero_stream
        except Exception as exc:
            self._demote_to_webrtc_or_energy(f"silero failed ({exc}), using fallback")
            return None

    def _demote_to_webrtc_or_energy(self, detail: str) -> None:
        if webrtcvad is not None:
            self._webrtc_vad = webrtcvad.Vad(self._aggressiveness)
            self.backend_name = "webrtc"
            self.backend_detail = f"{detail}; webrtcvad aggressiveness={self._aggressiveness}"
            return
        self._demote_to_energy(detail)

    def _demote_to_energy(self, detail: str) -> None:
        self.backend_name = "energy"
        self.backend_detail = detail
        self._webrtc_vad = None
        self._silero_vad = None
        self._silero_stream = None
