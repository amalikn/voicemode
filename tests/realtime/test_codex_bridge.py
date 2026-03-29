from python_voicemode.realtime.codex_bridge import _extract_codex_text


def test_extract_codex_text_from_item_completed_jsonl():
    text = "\n".join(
        [
            '{"type":"thread.started","thread_id":"abc"}',
            '{"type":"turn.started"}',
            '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"OK"}}',
            '{"type":"turn.completed"}',
        ]
    )

    assert _extract_codex_text(text) == "OK"


def test_extract_codex_text_from_nested_content_list():
    text = (
        '{"type":"item.completed","item":{"type":"agent_message","content":['
        '{"type":"output_text","text":"First line."},'
        '{"type":"output_text","text":"Second line."}'
        "]}}"
    )

    assert _extract_codex_text(text) == "First line.\nSecond line."
