import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
import pytest


class DummySoundDevice(ModuleType):
    def __init__(self):
        super().__init__("sounddevice")
        self.InputStream = object
        self.OutputStream = object
        self.default = SimpleNamespace(device=[None, None])

    def __getattr__(self, name):
        raise AttributeError(name)


@pytest.fixture(autouse=True)
def stub_audio_runtime_modules(monkeypatch):
    """Keep runtime imports isolated from host audio hardware."""
    monkeypatch.setitem(sys.modules, "sounddevice", DummySoundDevice())
    monkeypatch.setitem(sys.modules, "aiohttp", __import__("aiohttp"))
    yield


@pytest.fixture
def temp_config_dir(tmp_path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    return runtime_dir
