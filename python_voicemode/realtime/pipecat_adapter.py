"""Optional Pipecat adapter surface for realtime orchestration."""

from __future__ import annotations

from importlib.util import find_spec


class PipecatOrchestratorAdapter:
    """Track whether Pipecat is available for advanced orchestration hooks."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def health(self) -> tuple[bool, str]:
        if not self.enabled:
            return True, "disabled"
        if find_spec("pipecat") is None:
            return False, "pipecat-ai is not installed"
        return True, "pipecat is available for adapter integration"
