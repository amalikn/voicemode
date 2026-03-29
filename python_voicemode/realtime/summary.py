"""Spoken output planning for voice responses."""

from __future__ import annotations

import re

from .models import RouteTarget, SpokenOutputMode, SpokenPlan


def _first_sentences(text: str, max_sentences: int = 2) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences]).strip()


class SpokenResponsePlanner:
    """Choose between full, summary, and chunked spoken output."""

    def __init__(self, summary_threshold_words: int, voice_shell=None):
        self.summary_threshold_words = summary_threshold_words
        self.voice_shell = voice_shell

    async def plan(
        self,
        text: str,
        route: RouteTarget,
        *,
        read_aloud: bool = False,
        voice_enabled: bool = True,
    ) -> SpokenPlan:
        if not voice_enabled:
            return SpokenPlan(
                mode=SpokenOutputMode.NONE,
                text=text,
                spoken_text="",
                should_speak=False,
            )

        if read_aloud:
            return SpokenPlan(
                mode=SpokenOutputMode.CHUNKED,
                text=text,
                spoken_text=text,
                chunks=[text],
            )

        words = len(text.split())
        if words <= self.summary_threshold_words:
            return SpokenPlan(
                mode=SpokenOutputMode.FULL,
                text=text,
                spoken_text=text,
            )

        spoken_text = _first_sentences(text)
        if self.voice_shell is not None:
            spoken_text = await self.voice_shell.summarize_for_speech(text) or spoken_text
        if not spoken_text:
            spoken_text = text[:300]
        return SpokenPlan(
            mode=SpokenOutputMode.SUMMARY,
            text=text,
            spoken_text=spoken_text,
        )
