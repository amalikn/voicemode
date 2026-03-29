"""CLI commands for the event-driven local/hybrid voice runtime."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import click
import httpx

from python_voicemode.realtime.config import RealtimeVoiceConfig
from python_voicemode.realtime.ptt import write_hammerspoon_config

MODE_ALIASES = {
    "walk": "walkie-talkie",
    "walkie-talkie": "walkie-talkie",
    "convo": "conversational",
    "conversational": "conversational",
}


async def _request_json(config: RealtimeVoiceConfig, method: str, path: str, payload: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.request(method, f"{config.control_base_url}{path}", json=payload)
        response.raise_for_status()
        return response.json()


def normalize_mode_value(mode: str) -> str:
    return MODE_ALIASES.get(mode, mode)


async def dispatch_voice_control_async(event: str, mode: str | None = None) -> dict:
    config = RealtimeVoiceConfig.load()
    payload = {"event": event}
    if mode:
        payload["mode"] = normalize_mode_value(mode)
    return await _request_json(config, "POST", "/control", payload)


def dispatch_voice_control(event: str, mode: str | None = None) -> dict:
    return asyncio.run(dispatch_voice_control_async(event, mode))


async def dispatch_voice_read_async(path: Path) -> dict:
    config = RealtimeVoiceConfig.load()
    return await _request_json(config, "POST", "/read-file", {"path": str(path)})


def dispatch_voice_read(path: Path) -> dict:
    return asyncio.run(dispatch_voice_read_async(path))


@click.group()
@click.help_option("-h", "--help")
def voice():
    """Run the explicit local/hybrid voice runtime."""
    pass


@voice.command("run")
@click.option(
    "--mode",
    type=click.Choice(["walkie-talkie", "conversational"]),
    help="Initial mode for the runtime daemon.",
)
@click.option("--debug", is_flag=True, help="Enable runtime debug logging.")
def run_voice_runtime(mode: str | None, debug: bool) -> None:
    """Start the local control server, turn manager, and optional open-mic loop."""
    config = RealtimeVoiceConfig.load()
    if mode is not None:
        config = replace(config, mode=config.mode.__class__(mode))
    from python_voicemode.realtime.logging_runtime import setup_runtime_logging
    from python_voicemode.realtime.orchestrator import VoiceRuntimeServer

    setup_runtime_logging(config.logs_dir, debug=debug)
    server = VoiceRuntimeServer(config)

    async def runner() -> None:
        click.echo(await server.launcher.readiness_text())
        await server.run_forever()

    asyncio.run(runner())


@voice.command("status")
def voice_status() -> None:
    """Show current runtime mode/state from the local control server."""
    config = RealtimeVoiceConfig.load()
    try:
        payload = asyncio.run(_request_json(config, "GET", "/status"))
    except Exception as exc:  # pragma: no cover - network failure path
        click.echo(f"Voice runtime is not reachable at {config.control_base_url}: {exc}")
        raise SystemExit(1)
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


@voice.command("diag")
def voice_diag() -> None:
    """Show runtime diagnostics or local readiness when the daemon is offline."""
    config = RealtimeVoiceConfig.load()
    try:
        payload = asyncio.run(_request_json(config, "GET", "/diag"))
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    except Exception:
        pass
    from python_voicemode.realtime.orchestrator import VoiceRuntimeServer

    server = VoiceRuntimeServer(config)
    click.echo(asyncio.run(server.launcher.readiness_text()))
    click.echo("\nLast 20 events:")
    click.echo(json.dumps(server.session_store.recent_events(), indent=2, sort_keys=True))


@voice.command("control")
@click.argument(
    "event",
    type=click.Choice(
        [
            "PTT_DOWN",
            "PTT_UP",
            "TTS_STOP",
            "READ_CONTINUE",
            "READ_REPEAT",
            "READ_SKIP",
            "READ_SUMMARIZE",
            "READ_STOP",
            "MODE_SWITCH",
        ]
    ),
)
@click.option("--mode", type=click.Choice(["walkie-talkie", "conversational"]), help="Mode for MODE_SWITCH.")
def voice_control(event: str, mode: str | None) -> None:
    """Send a control event to the local runtime."""
    response = dispatch_voice_control(event, mode)
    click.echo(json.dumps(response, indent=2, sort_keys=True))


@voice.command("read")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def voice_read(path: Path) -> None:
    """Read a file aloud through the running daemon."""
    response = dispatch_voice_read(path)
    click.echo(json.dumps(response, indent=2, sort_keys=True))


@voice.command("export-hammerspoon")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path.home() / ".hammerspoon" / "voicemode.lua",
    show_default=True,
    help="Destination for the generated Hammerspoon config.",
)
def export_hammerspoon(output: Path) -> None:
    """Generate a Hammerspoon script for global hotkeys and status."""
    config = RealtimeVoiceConfig.load()
    path = write_hammerspoon_config(config, output)
    click.echo(str(path))
