import pytest

from python_voicemode.realtime.pipecat_adapter import PipecatOrchestratorAdapter


@pytest.mark.asyncio
async def test_pipecat_health_reports_disabled():
    adapter = PipecatOrchestratorAdapter(enabled=False)

    ok, detail = await adapter.health()

    assert ok is True
    assert detail == "disabled"
