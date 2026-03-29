"""Short MCP tool aliases for the most common VoiceMode actions."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Union

from python_voicemode.cli_commands.voice import dispatch_voice_control_async, dispatch_voice_read_async
from python_voicemode.server import mcp
from python_voicemode.tools.converse import converse as converse_tool


@mcp.tool()
async def chat(
    message: str,
    wait_for_response: Union[bool, str] = True,
    listen_duration_max: float = 120.0,
    listen_duration_min: float = 2.0,
    timeout: float = 60.0,
    voice: Optional[str] = None,
    tts_provider: Optional[Literal["openai", "kokoro"]] = None,
    tts_model: Optional[str] = None,
    tts_instructions: Optional[str] = None,
    chime_enabled: Optional[Union[bool, str]] = None,
    audio_format: Optional[str] = None,
    disable_silence_detection: Union[bool, str] = False,
    speed: Optional[float] = None,
    vad_aggressiveness: Optional[Union[int, str]] = None,
    skip_tts: Optional[Union[bool, str]] = None,
    chime_leading_silence: Optional[float] = None,
    chime_trailing_silence: Optional[float] = None,
    metrics_level: Optional[Literal["minimal", "summary", "verbose"]] = None,
    wait_for_conch: Union[bool, str] = False,
) -> str:
    """Short alias for the `converse` MCP tool."""

    return await converse_tool.fn(
        message=message,
        wait_for_response=wait_for_response,
        listen_duration_max=listen_duration_max,
        listen_duration_min=listen_duration_min,
        timeout=timeout,
        voice=voice,
        tts_provider=tts_provider,
        tts_model=tts_model,
        tts_instructions=tts_instructions,
        chime_enabled=chime_enabled,
        audio_format=audio_format,
        disable_silence_detection=disable_silence_detection,
        speed=speed,
        vad_aggressiveness=vad_aggressiveness,
        skip_tts=skip_tts,
        chime_leading_silence=chime_leading_silence,
        chime_trailing_silence=chime_trailing_silence,
        metrics_level=metrics_level,
        wait_for_conch=wait_for_conch,
    )


@mcp.tool()
async def read(path: str) -> dict:
    """Short alias for reading a file aloud through the running voice runtime."""

    source = Path(path).expanduser()
    if not source.exists():
        return {"accepted": False, "error": f"Path does not exist: {source}"}
    if source.is_dir():
        return {"accepted": False, "error": f"Path must be a file, not a directory: {source}"}
    return await dispatch_voice_read_async(source)


@mcp.tool()
async def mode(mode: Literal["walk", "walkie-talkie", "convo", "conversational"]) -> dict:
    """Short alias for switching the running voice runtime mode."""

    return await dispatch_voice_control_async("MODE_SWITCH", mode)


@mcp.tool()
async def stop() -> dict:
    """Short alias for stopping current speech or read-aloud playback."""

    return await dispatch_voice_control_async("TTS_STOP")
