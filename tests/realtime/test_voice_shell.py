import pytest

from python_voicemode.realtime.voice_shell import OllamaVoiceShell


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payload):
        self.payload = payload
        self.last_post_json = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _url):
        return _FakeResponse(self.payload)

    async def post(self, _url, json):
        self.last_post_json = json
        return _FakeResponse({"response": "ok"})


@pytest.mark.asyncio
async def test_voice_shell_health_reports_installed_model(monkeypatch):
    monkeypatch.setattr(
        "python_voicemode.realtime.voice_shell.httpx.AsyncClient",
        lambda timeout=3.0: _FakeAsyncClient({"models": [{"name": "phi4-mini"}]}),
    )

    shell = OllamaVoiceShell("http://127.0.0.1:11434", "phi4-mini")
    ok, detail = await shell.health()

    assert ok is True
    assert "phi4-mini" in detail


@pytest.mark.asyncio
async def test_voice_shell_health_reports_missing_model(monkeypatch):
    monkeypatch.setattr(
        "python_voicemode.realtime.voice_shell.httpx.AsyncClient",
        lambda timeout=3.0: _FakeAsyncClient({"models": [{"name": "qwen2.5-coder:7b"}]}),
    )

    shell = OllamaVoiceShell("http://127.0.0.1:11434", "phi4-mini")
    ok, detail = await shell.health()

    assert ok is False
    assert "not installed" in detail


@pytest.mark.asyncio
async def test_voice_shell_health_accepts_latest_tag_for_untagged_model(monkeypatch):
    monkeypatch.setattr(
        "python_voicemode.realtime.voice_shell.httpx.AsyncClient",
        lambda timeout=3.0: _FakeAsyncClient({"models": [{"name": "phi4-mini:latest"}]}),
    )

    shell = OllamaVoiceShell("http://127.0.0.1:11434", "phi4-mini")
    ok, detail = await shell.health()

    assert ok is True
    assert "phi4-mini:latest" in detail


@pytest.mark.asyncio
async def test_voice_shell_generate_uses_resolved_latest_model(monkeypatch):
    client = _FakeAsyncClient({"models": [{"name": "phi4-mini:latest"}]})
    monkeypatch.setattr(
        "python_voicemode.realtime.voice_shell.httpx.AsyncClient",
        lambda timeout=15.0: client,
    )

    shell = OllamaVoiceShell("http://127.0.0.1:11434", "phi4-mini")
    result = await shell.answer_short("hello")

    assert result == "ok"
    assert client.last_post_json is not None
    assert client.last_post_json["model"] == "phi4-mini:latest"
