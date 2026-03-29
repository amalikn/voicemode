from types import SimpleNamespace

import numpy as np
import pytest

import python_voicemode.realtime.vad as vad_module
from python_voicemode.realtime.vad import StreamingVad


class FakeWebRtcVad:
    def __init__(self, aggressiveness: int):
        self.aggressiveness = aggressiveness

    def is_speech(self, chunk: bytes, sample_rate: int) -> bool:
        return any(chunk) and sample_rate == 16000


class FakeChan:
    def __init__(self, events):
        self.events = list(events)

    def recv_nowait(self):
        if not self.events:
            raise vad_module.ChanEmpty()
        return self.events.pop(0)


class FakeSileroStream:
    def __init__(self, events):
        self._event_ch = FakeChan(events)
        self.frames = []
        self.closed = False

    def push_frame(self, frame):
        self.frames.append(frame)

    async def aclose(self):
        self.closed = True


class FakeSileroVad:
    def __init__(self, events):
        self.events = events
        self.stream_instance = FakeSileroStream(events)

    def stream(self):
        return self.stream_instance


@pytest.mark.asyncio
async def test_streaming_vad_auto_prefers_silero(monkeypatch):
    fake_backend = FakeSileroVad([])
    monkeypatch.setattr(
        vad_module,
        "livekit_silero",
        SimpleNamespace(VAD=SimpleNamespace(load=lambda **_: fake_backend)),
    )
    monkeypatch.setattr(vad_module, "rtc", SimpleNamespace(AudioFrame=lambda **kwargs: SimpleNamespace(**kwargs)))
    monkeypatch.setattr(vad_module, "VADEventType", SimpleNamespace(START_OF_SPEECH="start", END_OF_SPEECH="end"))
    monkeypatch.setattr(vad_module, "webrtcvad", SimpleNamespace(Vad=FakeWebRtcVad))

    vad = StreamingVad(energy_threshold=0.5, backend="auto", aggressiveness=3)

    assert vad.backend_name == "silero"
    ok, detail = vad.health()
    assert ok is True
    assert "silero" in detail
    await vad.aclose()


@pytest.mark.asyncio
async def test_streaming_vad_falls_back_to_webrtc_when_silero_load_fails(monkeypatch):
    def broken_load(**_):
        raise RuntimeError("no model")

    monkeypatch.setattr(
        vad_module,
        "livekit_silero",
        SimpleNamespace(VAD=SimpleNamespace(load=broken_load)),
    )
    monkeypatch.setattr(vad_module, "rtc", SimpleNamespace(AudioFrame=lambda **kwargs: SimpleNamespace(**kwargs)))
    monkeypatch.setattr(vad_module, "VADEventType", SimpleNamespace(START_OF_SPEECH="start", END_OF_SPEECH="end"))
    monkeypatch.setattr(vad_module, "webrtcvad", SimpleNamespace(Vad=FakeWebRtcVad))

    vad = StreamingVad(energy_threshold=0.9, backend="auto")
    transition = await vad.process_frame(np.ones(480, dtype=np.float32))

    assert vad.backend_name == "webrtc"
    assert transition.speech_started is True


@pytest.mark.asyncio
async def test_streaming_vad_webrtc_detects_speech_and_end(monkeypatch):
    monkeypatch.setattr(vad_module, "livekit_silero", None)
    monkeypatch.setattr(vad_module, "webrtcvad", SimpleNamespace(Vad=FakeWebRtcVad))
    vad = StreamingVad(energy_threshold=0.9, backend="webrtc", silence_frames=1)

    speech_frame = np.ones(480, dtype=np.float32)
    silence_frame = np.zeros(480, dtype=np.float32)

    started = await vad.process_frame(speech_frame)
    ended = await vad.process_frame(silence_frame)

    assert started.speech_started is True
    assert ended.speech_ended is True


@pytest.mark.asyncio
async def test_streaming_vad_silero_events_map_to_transitions(monkeypatch):
    start_event = SimpleNamespace(type="start")
    end_event = SimpleNamespace(type="end")
    fake_backend = FakeSileroVad([start_event, end_event])

    monkeypatch.setattr(
        vad_module,
        "livekit_silero",
        SimpleNamespace(VAD=SimpleNamespace(load=lambda **_: fake_backend)),
    )
    monkeypatch.setattr(vad_module, "rtc", SimpleNamespace(AudioFrame=lambda **kwargs: SimpleNamespace(**kwargs)))
    monkeypatch.setattr(vad_module, "VADEventType", SimpleNamespace(START_OF_SPEECH="start", END_OF_SPEECH="end"))
    monkeypatch.setattr(vad_module, "webrtcvad", None)

    vad = StreamingVad(energy_threshold=0.9, backend="silero")
    transition = await vad.process_frame(np.ones(480, dtype=np.float32))

    assert transition.speech_started is True
    assert transition.speech_ended is True
    await vad.aclose()
