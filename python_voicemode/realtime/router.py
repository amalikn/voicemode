"""Heuristic routing between local shell, Codex, and read-aloud paths."""

from __future__ import annotations

from .models import RouteDecision, RouteTarget


READ_COMMANDS = {
    "continue": "continue",
    "continue reading": "continue",
    "repeat last chunk": "repeat",
    "repeat that": "repeat",
    "skip ahead": "skip",
    "skip next section": "skip",
    "stop reading": "stop",
    "summarize instead": "summarize",
    "summarize what you just read": "summarize",
}

LOCAL_ONLY_PHRASES = {
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank you",
    "okay",
    "ok",
    "got it",
    "goodbye",
    "bye",
}


class RouteClassifier:
    """Fast routing heuristics with optional local-model refinement."""

    def __init__(self, voice_shell=None):
        self.voice_shell = voice_shell

    async def decide(self, text: str, read_aloud_active: bool = False) -> RouteDecision:
        normalized = " ".join(text.lower().strip().split())
        if not normalized:
            return RouteDecision(RouteTarget.LOCAL, "empty input")
        for phrase, command in READ_COMMANDS.items():
            if phrase in normalized:
                return RouteDecision(RouteTarget.READ_ALOUD, f"matched read command '{phrase}'", command)
        if any(
            phrase in normalized
            for phrase in (
                "read this markdown",
                "read the file",
                "read that response",
                "read aloud",
            )
        ):
            return RouteDecision(RouteTarget.READ_ALOUD, "explicit read-aloud request", "read")

        code_keywords = (
            "code",
            "repo",
            "bug",
            "refactor",
            "shell",
            "file",
            "commit",
            "plan",
            "project",
            "task",
            "tool",
            "python",
            "typescript",
            "markdown",
        )
        if any(keyword in normalized for keyword in code_keywords):
            return RouteDecision(RouteTarget.CODEX, "coding or repo-oriented request")

        if read_aloud_active and any(word in normalized for word in ("continue", "repeat", "summarize", "skip", "stop")):
            return RouteDecision(RouteTarget.READ_ALOUD, "read session command", "continue")

        if self.voice_shell is not None:
            hint = await self.voice_shell.route_hint(text)
            if hint == "codex":
                return RouteDecision(RouteTarget.CODEX, "local voice-shell escalation")
            if hint == "read_aloud":
                return RouteDecision(RouteTarget.READ_ALOUD, "local voice-shell read-aloud")
            if hint == "local":
                return RouteDecision(RouteTarget.LOCAL, "local voice-shell lightweight turn")

        if normalized in LOCAL_ONLY_PHRASES:
            return RouteDecision(RouteTarget.LOCAL, "brief acknowledgement or greeting")

        return RouteDecision(RouteTarget.CODEX, "default deep-turn routing")
