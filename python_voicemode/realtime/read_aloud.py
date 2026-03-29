"""Interruptible read-aloud support for markdown and plain text."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

from .models import ReadDocument
from .session_store import SessionStore


def _strip_markdown(text: str) -> str:
    text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _chunk_text(text: str, word_limit: int) -> list[str]:
    sections = []
    current: list[str] = []
    current_words = 0
    for paragraph in [part.strip() for part in text.split("\n\n") if part.strip()]:
        words = paragraph.split()
        if current and current_words + len(words) > word_limit:
            sections.append("\n\n".join(current))
            current = [paragraph]
            current_words = len(words)
        else:
            current.append(paragraph)
            current_words += len(words)
    if current:
        sections.append("\n\n".join(current))
    return sections


class ReadAloudController:
    """Prepare, persist, and resume chunked reading."""

    def __init__(self, session_store: SessionStore, word_limit: int):
        self.session_store = session_store
        self.word_limit = word_limit
        self.document: Optional[ReadDocument] = None

    @property
    def is_active(self) -> bool:
        return self.document is not None and bool(self.document.chunks)

    def load_text(self, title: str, text: str, source_path: Path | None = None) -> ReadDocument:
        clean_text = _strip_markdown(text)
        document_id = hashlib.sha1(f"{title}:{source_path}:{clean_text[:500]}".encode()).hexdigest()
        chunks = _chunk_text(clean_text, self.word_limit)
        saved = self.session_store.load_read_progress(document_id)
        cursor = saved["cursor"] if saved else 0
        self.document = ReadDocument(
            document_id=document_id,
            source_path=source_path,
            title=title,
            chunks=chunks,
            cursor=min(cursor, max(len(chunks) - 1, 0)),
        )
        self._save()
        return self.document

    def load_file(self, path: Path) -> ReadDocument:
        return self.load_text(path.name, path.read_text(encoding="utf-8"), path)

    def current_chunk(self) -> str | None:
        if not self.is_active or self.document is None:
            return None
        return self.document.chunks[self.document.cursor]

    def advance(self) -> str | None:
        if not self.is_active or self.document is None:
            return None
        if self.document.cursor < len(self.document.chunks) - 1:
            self.document.cursor += 1
            self._save()
            return self.document.chunks[self.document.cursor]
        return None

    def repeat_last(self) -> str | None:
        return self.current_chunk()

    def skip_next_section(self) -> str | None:
        if not self.is_active or self.document is None:
            return None
        self.document.cursor = min(self.document.cursor + 1, len(self.document.chunks) - 1)
        self._save()
        return self.current_chunk()

    def summarize_context(self) -> str:
        if not self.is_active or self.document is None:
            return "Nothing is currently being read aloud."
        current = self.current_chunk() or ""
        return f"Currently reading {self.document.title}. Last chunk: {current[:300]}".strip()

    def stop(self) -> None:
        self._save()
        self.document = None

    def _save(self) -> None:
        if self.document is None:
            return
        self.session_store.save_read_progress(
            document_id=self.document.document_id,
            title=self.document.title,
            source_path=str(self.document.source_path) if self.document.source_path else None,
            cursor=self.document.cursor,
            details={"chunks": len(self.document.chunks)},
        )
