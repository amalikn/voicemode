from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


class _FakeMCP:
    def tool(self):
        def decorator(func):
            func.fn = func
            return func

        return decorator


def _load_shortcuts_module():
    fake_server = ModuleType("python_voicemode.server")
    fake_server.mcp = _FakeMCP()
    sys.modules["python_voicemode.server"] = fake_server

    fake_converse_module = ModuleType("python_voicemode.tools.converse")

    async def fake_converse(**kwargs):
        return "ok"

    fake_converse_module.converse = SimpleNamespace(fn=fake_converse)
    sys.modules["python_voicemode.tools.converse"] = fake_converse_module

    module_path = Path("/Volumes/Data/_ai/_mcp/mcp_stuff/voicemode/python_voicemode/tools/shortcuts.py")
    spec = spec_from_file_location("test_shortcuts_module", module_path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_shortcut_mode_uses_async_runtime_dispatch(monkeypatch):
    shortcuts = _load_shortcuts_module()
    calls = []

    async def fake_dispatch(event, mode=None):
        calls.append((event, mode))
        return {"accepted": True, "event": event, "mode": mode}

    monkeypatch.setattr(shortcuts, "dispatch_voice_control_async", fake_dispatch)

    result = await shortcuts.mode.fn("convo")

    assert result["accepted"] is True
    assert calls == [("MODE_SWITCH", "convo")]


@pytest.mark.asyncio
async def test_shortcut_stop_uses_async_runtime_dispatch(monkeypatch):
    shortcuts = _load_shortcuts_module()
    calls = []

    async def fake_dispatch(event, mode=None):
        calls.append((event, mode))
        return {"accepted": True, "event": event}

    monkeypatch.setattr(shortcuts, "dispatch_voice_control_async", fake_dispatch)

    result = await shortcuts.stop.fn()

    assert result["accepted"] is True
    assert calls == [("TTS_STOP", None)]


@pytest.mark.asyncio
async def test_shortcut_read_uses_async_runtime_dispatch(monkeypatch, tmp_path):
    shortcuts = _load_shortcuts_module()
    calls = []

    async def fake_dispatch(path: Path):
        calls.append(path)
        return {"accepted": True, "path": str(path)}

    monkeypatch.setattr(shortcuts, "dispatch_voice_read_async", fake_dispatch)

    source = tmp_path / "notes.md"
    source.write_text("hello", encoding="utf-8")

    result = await shortcuts.read.fn(str(source))

    assert result["accepted"] is True
    assert calls == [source]


@pytest.mark.asyncio
async def test_shortcut_read_rejects_missing_or_directory_paths(tmp_path):
    shortcuts = _load_shortcuts_module()
    missing = tmp_path / "missing.md"
    directory = tmp_path / "folder"
    directory.mkdir()

    missing_result = await shortcuts.read.fn(str(missing))
    directory_result = await shortcuts.read.fn(str(directory))

    assert missing_result["accepted"] is False
    assert "Path does not exist" in missing_result["error"]
    assert directory_result["accepted"] is False
    assert "must be a file" in directory_result["error"]
