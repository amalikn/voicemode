"""Microphone capture primitives for push-to-talk and open-mic modes."""

from __future__ import annotations

import asyncio
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


def _float_to_int16(frame: np.ndarray) -> np.ndarray:
    clipped = np.clip(frame, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16)


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = _float_to_int16(samples)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return path


class PushToTalkRecorder:
    """Collect microphone audio between explicit start and stop calls."""

    def __init__(self, sample_rate: int = 16_000):
        self.sample_rate = sample_rate
        self.stream: sd.InputStream | None = None
        self.frames: list[np.ndarray] = []

    @property
    def active(self) -> bool:
        return self.stream is not None

    def start(self) -> None:
        if self.stream is not None:
            return
        self.frames = []

        def callback(indata, _frames, _time, status):
            if status:
                return
            self.frames.append(indata.copy())

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self.stream.start()

    def stop(self, output_path: Path) -> Path:
        if self.stream is None:
            raise RuntimeError("recorder is not active")
        self.stream.stop()
        self.stream.close()
        self.stream = None
        if not self.frames:
            raise RuntimeError("no microphone frames were captured")
        samples = np.concatenate(self.frames, axis=0).reshape(-1)
        return write_wav(output_path, samples, self.sample_rate)


class OpenMicStream:
    """Background microphone stream for conversational VAD mode."""

    def __init__(self, sample_rate: int = 16_000, blocksize: int = 1024):
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.stream: sd.InputStream | None = None
        self.queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        if self.stream is not None:
            return
        self.loop = asyncio.get_running_loop()

        def callback(indata, _frames, _time, status):
            if status or self.loop is None:
                return
            frame = indata.copy().reshape(-1)
            self.loop.call_soon_threadsafe(self.queue.put_nowait, frame)

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.blocksize,
            callback=callback,
        )
        self.stream.start()

    async def read_frame(self) -> np.ndarray:
        return await self.queue.get()

    async def stop(self) -> None:
        if self.stream is None:
            return
        self.stream.stop()
        self.stream.close()
        self.stream = None
