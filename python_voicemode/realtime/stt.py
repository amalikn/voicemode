"""whisper.cpp/OpenAI-compatible STT adapter."""

from __future__ import annotations

from pathlib import Path

import httpx
from openai import AsyncOpenAI


class WhisperCppSTTAdapter:
    """Transcribe audio files using an OpenAI-compatible STT endpoint."""

    def __init__(self, base_url: str, model: str = "whisper-1"):
        self.base_url = base_url
        self.model = model
        self.client = AsyncOpenAI(api_key="not-needed-for-local", base_url=base_url, max_retries=0)

    async def health(self) -> tuple[bool, str]:
        url = self.base_url.rstrip("/")
        candidates = [f"{url}/health", url.rstrip("/v1"), url]
        async with httpx.AsyncClient(timeout=3.0) as client:
            for candidate in candidates:
                try:
                    response = await client.get(candidate)
                    if response.status_code < 500:
                        return True, f"reachable at {candidate}"
                except httpx.HTTPError:
                    continue
        return False, f"unreachable: {self.base_url}"

    async def transcribe_file(self, audio_path: Path) -> str:
        with audio_path.open("rb") as handle:
            response = await self.client.audio.transcriptions.create(
                model=self.model,
                file=handle,
            )
        return getattr(response, "text", "").strip()
