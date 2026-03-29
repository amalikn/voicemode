import importlib
import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

from click.testing import CliRunner


class DummySoundDevice(ModuleType):
    def __init__(self):
        super().__init__("sounddevice")
        self.InputStream = object
        self.OutputStream = object
        self.default = SimpleNamespace(device=[None, None])


def test_voice_cli_help_exposes_runtime_commands(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", DummySoundDevice())
    cli = importlib.import_module("python_voicemode.cli")
    runner = CliRunner()

    result = runner.invoke(cli.python_voicemode_main_cli, ["--help"])

    assert result.exit_code == 0
    assert "voice" in result.output
    assert "status" in result.output
    assert "diag" in result.output
    assert "chat" in result.output
    assert "read" in result.output
    assert "mode" in result.output
    assert "stop" in result.output


def test_voice_status_and_control_commands_use_runtime_endpoint(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", DummySoundDevice())
    cli = importlib.import_module("python_voicemode.cli")
    voice_cli = importlib.import_module("python_voicemode.cli_commands.voice")
    runner = CliRunner()
    calls = []

    async def fake_request(config, method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/status":
            return {"mode": "walkie-talkie", "state": "IDLE"}
        return {"accepted": True, "event": payload["event"]}

    monkeypatch.setattr(voice_cli, "_request_json", fake_request)

    status_result = runner.invoke(cli.python_voicemode_main_cli, ["voice", "status"])
    control_result = runner.invoke(
        cli.python_voicemode_main_cli,
        ["voice", "control", "MODE_SWITCH", "--mode", "conversational"],
    )

    assert status_result.exit_code == 0
    assert '"state": "IDLE"' in status_result.output
    assert control_result.exit_code == 0
    assert calls[0][0:2] == ("GET", "/status")
    assert calls[1] == ("POST", "/control", {"event": "MODE_SWITCH", "mode": "conversational"})


def test_voice_diag_uses_live_payload_when_runtime_is_reachable(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", DummySoundDevice())
    cli = importlib.import_module("python_voicemode.cli")
    voice_cli = importlib.import_module("python_voicemode.cli_commands.voice")
    runner = CliRunner()

    async def fake_request(config, method, path, payload=None):
        return {"mode": "walkie-talkie", "state": "IDLE", "diagnostics": {"total_events": 2}}

    monkeypatch.setattr(voice_cli, "_request_json", fake_request)

    result = runner.invoke(cli.python_voicemode_main_cli, ["voice", "diag"])

    assert result.exit_code == 0
    assert '"total_events": 2' in result.output


def test_voice_read_and_export_hammerspoon(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "sounddevice", DummySoundDevice())
    cli = importlib.import_module("python_voicemode.cli")
    voice_cli = importlib.import_module("python_voicemode.cli_commands.voice")
    runner = CliRunner()
    calls = []

    async def fake_request(config, method, path, payload=None):
        calls.append((method, path, payload))
        return {"accepted": True, "path": payload["path"]}

    def fake_write(config, output_path):
        output_path.write_text("-- hammerspoon config", encoding="utf-8")
        return output_path

    monkeypatch.setattr(voice_cli, "_request_json", fake_request)
    monkeypatch.setattr(voice_cli, "write_hammerspoon_config", fake_write)

    source = tmp_path / "notes.md"
    source.write_text("# Heading", encoding="utf-8")
    output = tmp_path / "voicemode.lua"

    read_result = runner.invoke(cli.python_voicemode_main_cli, ["voice", "read", str(source)])
    export_result = runner.invoke(cli.python_voicemode_main_cli, ["voice", "export-hammerspoon", "--output", str(output)])

    assert read_result.exit_code == 0
    assert calls[0] == ("POST", "/read-file", {"path": str(source)})
    assert export_result.exit_code == 0
    assert str(output) in export_result.output
    assert output.read_text(encoding="utf-8") == "-- hammerspoon config"


def test_render_hammerspoon_config_emits_valid_lua_modifier_table():
    from python_voicemode.realtime.config import RealtimeVoiceConfig
    from python_voicemode.realtime.ptt import render_hammerspoon_config

    rendered = render_hammerspoon_config(RealtimeVoiceConfig.load())

    assert "hs.hotkey.bind({\"cmd\", \"shift\"}, \"space\", function()" in rendered
    assert "[\"cmd\", \"shift\"]" not in rendered
    assert 'setTransientStatus("VM REC", "Push-to-talk recording")' in rendered
    assert 'setTransientStatus("VM THINK", "Processing the recorded turn")' in rendered


def test_short_runtime_aliases_use_existing_runtime_requests(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "sounddevice", DummySoundDevice())
    cli = importlib.import_module("python_voicemode.cli")
    voice_cli = importlib.import_module("python_voicemode.cli_commands.voice")
    runner = CliRunner()
    calls = []

    async def fake_request(config, method, path, payload=None):
        calls.append((method, path, payload))
        return {"accepted": True, "path": payload.get("path"), "event": payload.get("event"), "mode": payload.get("mode")}

    monkeypatch.setattr(voice_cli, "_request_json", fake_request)

    source = tmp_path / "notes.md"
    source.write_text("# Heading", encoding="utf-8")

    read_result = runner.invoke(cli.python_voicemode_main_cli, ["read", str(source)])
    mode_result = runner.invoke(cli.python_voicemode_main_cli, ["mode", "walk"])
    stop_result = runner.invoke(cli.python_voicemode_main_cli, ["stop"])
    terse_mode_result = runner.invoke(cli.python_voicemode_main_cli, ["m", "convo"])
    terse_read_result = runner.invoke(cli.python_voicemode_main_cli, ["r", str(source)])
    terse_stop_result = runner.invoke(cli.python_voicemode_main_cli, ["x"])

    assert read_result.exit_code == 0
    assert mode_result.exit_code == 0
    assert stop_result.exit_code == 0
    assert terse_mode_result.exit_code == 0
    assert terse_read_result.exit_code == 0
    assert terse_stop_result.exit_code == 0
    assert calls[0] == ("POST", "/read-file", {"path": str(source)})
    assert calls[1] == ("POST", "/control", {"event": "MODE_SWITCH", "mode": "walkie-talkie"})
    assert calls[2] == ("POST", "/control", {"event": "TTS_STOP"})
    assert calls[3] == ("POST", "/control", {"event": "MODE_SWITCH", "mode": "conversational"})
    assert calls[4] == ("POST", "/read-file", {"path": str(source)})
    assert calls[5] == ("POST", "/control", {"event": "TTS_STOP"})


def test_mode_shortcut_rejects_invalid_choice(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", DummySoundDevice())
    cli = importlib.import_module("python_voicemode.cli")
    runner = CliRunner()

    result = runner.invoke(cli.python_voicemode_main_cli, ["mode", "invalid"])

    assert result.exit_code == 2
    assert "Invalid value" in result.output


def test_chat_alias_reuses_converse_options_and_behavior(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", DummySoundDevice())
    cli = importlib.import_module("python_voicemode.cli")
    runner = CliRunner()

    help_result = runner.invoke(cli.python_voicemode_main_cli, ["chat", "--help"])

    assert help_result.exit_code == 0
    assert "--continuous" in help_result.output
    assert "--wait / --no-wait" in help_result.output

    calls = []
    monkeypatch.setattr(cli, "_run_converse_cli", lambda *args: calls.append(args))

    result = runner.invoke(
        cli.python_voicemode_main_cli,
        ["chat", "--continuous", "-m", "Start here", "--skip-tts", "--duration", "3", "--min-duration", "1"],
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    forwarded = calls[0]
    assert forwarded[0] == "Start here"
    assert forwarded[1] is True
    assert forwarded[2] == 3.0
    assert forwarded[3] == 1.0
    assert forwarded[13] is True
    assert forwarded[14] is True
