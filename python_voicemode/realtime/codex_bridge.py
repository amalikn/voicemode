"""Adapter for delegating heavier requests to Codex."""

from __future__ import annotations

import asyncio
import json
import shlex
import shutil
from pathlib import Path
from typing import Any


class CommandCodexBridge:
    """Run Codex via the local CLI using a configurable command template."""

    def __init__(self, command_template: str, workspace_dir: Path):
        self.command_template = command_template
        self.workspace_dir = workspace_dir

    async def health(self) -> tuple[bool, str]:
        binary = shlex.split(self.command_template.format(workspace=self.workspace_dir))[0]
        if shutil.which(binary) is None:
            return False, f"{binary} is not installed"
        return True, f"{binary} is available"

    async def answer(self, prompt: str, timeout: float) -> str:
        command = shlex.split(self.command_template.format(workspace=self.workspace_dir))
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(prompt.encode("utf-8")),
            timeout=timeout,
        )
        if process.returncode not in (0, None):
            raise RuntimeError(stderr.decode("utf-8", errors="replace").strip() or "Codex command failed")
        text = stdout.decode("utf-8", errors="replace").strip()
        extracted = _extract_codex_text(text)
        if extracted:
            return extracted
        return text


def _extract_codex_text(text: str) -> str:
    """Extract the last assistant message from Codex JSONL output when present."""

    lines = [line for line in text.splitlines() if line.strip()]
    last_text = ""
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        extracted = _extract_text_from_payload(payload)
        if extracted:
            last_text = extracted
    return last_text.strip()


def _extract_text_from_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return ""

    for key in ("content", "message", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    item = payload.get("item")
    extracted = _extract_text_from_payload(item)
    if extracted:
        return extracted

    content = payload.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for entry in content:
            part = _extract_text_from_payload(entry)
            if part:
                parts.append(part)
        if parts:
            return "\n".join(parts).strip()

    return ""
