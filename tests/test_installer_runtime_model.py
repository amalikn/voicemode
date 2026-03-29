import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_ROOT = ROOT / "installer"
if str(INSTALLER_ROOT) not in sys.path:
    sys.path.insert(0, str(INSTALLER_ROOT))

from voicemode_install import cli as installer_cli


def test_check_ollama_runtime_model_reports_missing_ollama(monkeypatch):
    monkeypatch.setattr(installer_cli, "check_command_exists", lambda name: False)

    ok, detail = installer_cli.check_ollama_runtime_model("phi4-mini")

    assert ok is False
    assert detail == "Ollama is not installed"


def test_check_ollama_runtime_model_reports_missing_model(monkeypatch):
    monkeypatch.setattr(installer_cli, "check_command_exists", lambda name: True)

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, *args, **kwargs):
            return b'{"models":[{"name":"qwen2.5-coder:7b"}]}'

    monkeypatch.setattr(installer_cli.urllib.request, "urlopen", lambda *args, **kwargs: _Response())

    ok, detail = installer_cli.check_ollama_runtime_model("phi4-mini")

    assert ok is False
    assert "phi4-mini" in detail
    assert "not installed" in detail


def test_check_ollama_runtime_model_reports_installed_model(monkeypatch):
    monkeypatch.setattr(installer_cli, "check_command_exists", lambda name: True)

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, *args, **kwargs):
            return b'{"models":[{"name":"phi4-mini"}]}'

    monkeypatch.setattr(installer_cli.urllib.request, "urlopen", lambda *args, **kwargs: _Response())

    ok, detail = installer_cli.check_ollama_runtime_model("phi4-mini")

    assert ok is True
    assert "phi4-mini" in detail


def test_check_ollama_runtime_model_accepts_latest_tag_for_untagged_model(monkeypatch):
    monkeypatch.setattr(installer_cli, "check_command_exists", lambda name: True)

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, *args, **kwargs):
            return b'{"models":[{"name":"phi4-mini:latest"}]}'

    monkeypatch.setattr(installer_cli.urllib.request, "urlopen", lambda *args, **kwargs: _Response())

    ok, detail = installer_cli.check_ollama_runtime_model("phi4-mini")

    assert ok is True
    assert "phi4-mini:latest" in detail


def test_ensure_ollama_runtime_model_dry_run(monkeypatch):
    monkeypatch.setattr(
        installer_cli,
        "check_ollama_runtime_model",
        lambda model: (False, f"Ollama is running, but model '{model}' is not installed"),
    )

    assert installer_cli.ensure_ollama_runtime_model("phi4-mini", dry_run=True, non_interactive=False) is True


def test_ensure_ollama_runtime_model_non_interactive_warns(monkeypatch):
    monkeypatch.setattr(
        installer_cli,
        "check_ollama_runtime_model",
        lambda model: (False, f"Ollama is running, but model '{model}' is not installed"),
    )

    assert installer_cli.ensure_ollama_runtime_model("phi4-mini", dry_run=False, non_interactive=True) is False
