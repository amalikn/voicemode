"""Audio playback adapters for the realtime runtime."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path


class AudioPlayer:
    """Playback interface."""

    async def play(self, audio_path: Path) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    async def stop(self) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    async def wait(self, timeout: float | None = None) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


class MpvAudioPlayer(AudioPlayer):
    """Killable low-latency playback via mpv."""

    def __init__(self):
        self.binary = shutil.which("mpv")
        self.process: asyncio.subprocess.Process | None = None

    def is_available(self) -> bool:
        return self.binary is not None

    async def play(self, audio_path: Path) -> None:
        if self.binary is None:
            raise RuntimeError("mpv is not installed")
        await self.stop()
        self.process = await asyncio.create_subprocess_exec(
            self.binary,
            "--no-terminal",
            "--really-quiet",
            "--audio-display=no",
            "--keep-open=no",
            str(audio_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def stop(self) -> None:
        if self.process is None:
            return
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        self.process = None

    async def wait(self, timeout: float | None = None) -> None:
        if self.process is None:
            return
        await asyncio.wait_for(self.process.wait(), timeout=timeout)
        self.process = None


class NullAudioPlayer(AudioPlayer):
    """Text-only fallback."""

    async def play(self, audio_path: Path) -> None:
        _ = audio_path

    async def stop(self) -> None:
        return None

    async def wait(self, timeout: float | None = None) -> None:
        _ = timeout
        return None

    def is_available(self) -> bool:
        return False
