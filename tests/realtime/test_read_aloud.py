from pathlib import Path

from python_voicemode.realtime.read_aloud import ReadAloudController, _strip_markdown
from python_voicemode.realtime.session_store import SessionStore


def test_strip_markdown_removes_common_noise():
    text = "# Heading\n\n- item one\n- item two\n\n`code` and [link](https://example.com)"
    stripped = _strip_markdown(text)
    assert "Heading" in stripped
    assert "item one" in stripped
    assert "code" in stripped
    assert "link" in stripped
    assert "#" not in stripped


def test_read_aloud_chunks_and_resume_from_cursor(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    controller = ReadAloudController(store, word_limit=4)

    document = controller.load_text(
        "notes.md",
        "Alpha beta gamma delta.\n\nEpsilon zeta eta theta.\n\nIota kappa lambda mu.",
    )

    assert len(document.chunks) == 3
    assert controller.current_chunk() == document.chunks[0]
    assert controller.advance() == document.chunks[1]
    assert controller.repeat_last() == document.chunks[1]
    assert controller.skip_next_section() == document.chunks[2]

    controller.stop()

    resumed_controller = ReadAloudController(store, word_limit=4)
    resumed = resumed_controller.load_text(
        "notes.md",
        "Alpha beta gamma delta.\n\nEpsilon zeta eta theta.\n\nIota kappa lambda mu.",
    )
    assert resumed.cursor == 2
    assert resumed_controller.current_chunk() == document.chunks[2]


def test_read_aloud_summary_mentions_current_document(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    controller = ReadAloudController(store, word_limit=20)
    controller.load_text("plan.md", "First section.\n\nSecond section.")
    summary = controller.summarize_context()
    assert "plan.md" in summary
    assert "First section" in summary


def test_read_aloud_stop_preserves_resume_cursor(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    controller = ReadAloudController(store, word_limit=4)
    controller.load_text(
        "notes.md",
        "Alpha beta gamma delta.\n\nEpsilon zeta eta theta.\n\nIota kappa lambda mu.",
    )
    controller.advance()
    controller.stop()

    resumed_controller = ReadAloudController(store, word_limit=4)
    resumed = resumed_controller.load_text(
        "notes.md",
        "Alpha beta gamma delta.\n\nEpsilon zeta eta theta.\n\nIota kappa lambda mu.",
    )
    assert resumed.cursor == 1
