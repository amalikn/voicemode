"""Kokoro/OpenAI-compatible TTS adapter."""

from __future__ import annotations

from pathlib import Path

import httpx
from openai import AsyncOpenAI


class KokoroTTSAdapter:
    """Generate speech audio using an OpenAI-compatible TTS endpoint."""

    def __init__(self, base_url: str, model: str, voice: str, response_format: str = "mp3"):
        self.base_url = base_url
        self.model = model
        self.voice = voice
        self.response_format = response_format
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

    async def synthesize_to_file(self, text: str, output_path: Path) -> Path:
        response = await self.client.audio.speech.create(
            model=self.model,
            input=text,
            voice=self.voice,
            response_format=self.response_format,
        )
        content = getattr(response, "content", None)
        if content is None:
            read = getattr(response, "read", None)
            if callable(read):
                content = read()
        if content is None:
            raise RuntimeError("TTS response did not include audio content")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        return output_path
