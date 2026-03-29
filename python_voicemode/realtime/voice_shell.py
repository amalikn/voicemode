"""Local Ollama voice-shell helper for acknowledgements and summaries."""

from __future__ import annotations

from typing import Optional

import httpx


def _candidate_model_names(model: str) -> tuple[str, ...]:
    """Return equivalent Ollama model names to try for a configured model."""
    normalized = model.strip()
    if not normalized:
        return tuple()
    if ":" in normalized:
        base, tag = normalized.rsplit(":", 1)
        if tag == "latest":
            return (normalized, base)
        return (normalized,)
    return (normalized, f"{normalized}:latest")


def _resolve_installed_model_name(model: str, installed_models: set[str]) -> Optional[str]:
    """Resolve a configured model to an installed Ollama model name."""
    for candidate in _candidate_model_names(model):
        if candidate in installed_models:
            return candidate
    return None


class OllamaVoiceShell:
    """Small local model used for smoothing, routing hints, and spoken summaries."""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def _fetch_installed_models(self, client: httpx.AsyncClient) -> set[str]:
        response = await client.get(f"{self.base_url}/api/tags")
        response.raise_for_status()
        data = response.json()
        return {
            entry.get("name")
            for entry in data.get("models", [])
            if isinstance(entry, dict) and entry.get("name")
        }

    async def health(self) -> tuple[bool, str]:
        async with httpx.AsyncClient(timeout=3.0) as client:
            try:
                installed_models = await self._fetch_installed_models(client)
                resolved_model = _resolve_installed_model_name(self.model, installed_models)
                if resolved_model is None:
                    return False, f"reachable at {self.base_url}, but model '{self.model}' is not installed"
                return True, f"reachable at {self.base_url} with model '{resolved_model}'"
            except httpx.HTTPError as exc:
                return False, str(exc)

    async def _generate(self, prompt: str, system: str) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            installed_models = await self._fetch_installed_models(client)
            resolved_model = _resolve_installed_model_name(self.model, installed_models) or self.model
            payload = {
                "model": resolved_model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.2},
            }
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data.get("response", "")).strip()

    async def acknowledge(self, text: str) -> str:
        try:
            return await self._generate(
                prompt=text,
                system="Return a single short spoken acknowledgement under twelve words.",
            )
        except Exception:
            return "Checking that."

    async def summarize_for_speech(self, text: str) -> str:
        try:
            return await self._generate(
                prompt=text,
                system=(
                    "Summarize technical text for speech in two short sentences. "
                    "Keep implementation detail minimal and focus on the answer."
                ),
            )
        except Exception:
            return ""

    async def answer_short(self, text: str) -> str:
        try:
            return await self._generate(
                prompt=text,
                system=(
                    "You are a low-latency voice shell. Answer briefly, naturally, and safely. "
                    "If the request needs deep coding or repo reasoning, say so in one sentence."
                ),
            )
        except Exception:
            return "I heard that. This likely needs a deeper answer."

    async def route_hint(self, text: str) -> Optional[str]:
        try:
            result = await self._generate(
                prompt=text,
                system=(
                    "Classify the user request as exactly one token: local, codex, or read_aloud. "
                    "Use codex for coding, repo, shell, planning, or high-stakes tasks."
                ),
            )
        except Exception:
            return None
        lowered = result.strip().lower()
        if lowered in {"local", "codex", "read_aloud"}:
            return lowered
        return None
