"""Shared models for the realtime voice runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class VoiceMode(str, Enum):
    """High-level interaction modes."""

    WALKIE_TALKIE = "walkie-talkie"
    CONVERSATIONAL = "conversational"


class VoiceState(str, Enum):
    """Explicit runtime states."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    RECORDING = "RECORDING"
    TRANSCRIBING = "TRANSCRIBING"
    ROUTING = "ROUTING"
    WAITING_LOCAL = "WAITING_LOCAL"
    WAITING_CODEX = "WAITING_CODEX"
    PLAYING_TTS = "PLAYING_TTS"
    READING_CHUNK = "READING_CHUNK"
    INTERRUPTED = "INTERRUPTED"
    ERROR = "ERROR"


class VoiceEventType(str, Enum):
    """Events consumed by the turn manager."""

    PTT_DOWN = "PTT_DOWN"
    PTT_UP = "PTT_UP"
    VAD_SPEECH_START = "VAD_SPEECH_START"
    VAD_SPEECH_END = "VAD_SPEECH_END"
    TRANSCRIPT_READY = "TRANSCRIPT_READY"
    ROUTE_LOCAL = "ROUTE_LOCAL"
    ROUTE_CODEX = "ROUTE_CODEX"
    ROUTE_READ_ALOUD = "ROUTE_READ_ALOUD"
    TTS_START = "TTS_START"
    TTS_STOP = "TTS_STOP"
    BARGE_IN = "BARGE_IN"
    READ_CONTINUE = "READ_CONTINUE"
    READ_STOP = "READ_STOP"
    READ_SKIP = "READ_SKIP"
    READ_REPEAT = "READ_REPEAT"
    READ_SUMMARIZE = "READ_SUMMARIZE"
    TIMEOUT = "TIMEOUT"
    FAIL = "FAIL"
    STATE_TRANSITION = "STATE_TRANSITION"
    MODE_SWITCH = "MODE_SWITCH"


class RouteTarget(str, Enum):
    """Routing destinations."""

    LOCAL = "local"
    CODEX = "codex"
    READ_ALOUD = "read_aloud"
    CONTROL = "control"


class SpokenOutputMode(str, Enum):
    """Speech delivery modes."""

    NONE = "none"
    FULL = "full"
    SUMMARY = "summary"
    CHUNKED = "chunked"


@dataclass(frozen=True)
class StageTimeouts:
    """Per-stage timeout configuration."""

    recording_seconds: float = 30.0
    transcription_seconds: float = 20.0
    routing_seconds: float = 4.0
    local_llm_seconds: float = 8.0
    codex_seconds: float = 120.0
    tts_generation_seconds: float = 20.0
    playback_seconds: float = 90.0


@dataclass
class RouteDecision:
    """A routing decision for a user utterance."""

    target: RouteTarget
    reason: str
    command: Optional[str] = None


@dataclass
class SpokenPlan:
    """Speech plan derived from text output."""

    mode: SpokenOutputMode
    text: str
    spoken_text: str
    chunks: list[str] = field(default_factory=list)
    should_speak: bool = True


@dataclass
class HealthStatus:
    """Health result for a single dependency."""

    name: str
    ok: bool
    detail: str


@dataclass
class RuntimeSnapshot:
    """Current runtime status."""

    mode: VoiceMode
    state: VoiceState
    muted: bool
    current_session_id: str
    last_transcript: Optional[str] = None
    last_response: Optional[str] = None
    reading_document: Optional[str] = None
    reading_cursor: int = 0
    last_events: list[dict[str, Any]] = field(default_factory=list)
    health: list[HealthStatus] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReadDocument:
    """Text prepared for read-aloud playback."""

    document_id: str
    source_path: Optional[Path]
    title: str
    chunks: list[str]
    cursor: int = 0
