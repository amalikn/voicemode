from python_voicemode.realtime.session_store import SessionStore


def test_session_store_persists_events_and_read_progress(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session_id = store.create_session("walkie-talkie", {"source": "test"})
    store.record_event(session_id, "PTT_DOWN", "RECORDING", {"from": "IDLE", "to": "RECORDING"})
    store.save_read_progress("doc-1", "notes.md", "/tmp/notes.md", 3, {"chunks": 5})
    store.close_session(session_id)

    recent = store.recent_events()
    assert recent[0]["event_type"] == "PTT_DOWN"
    progress = store.load_read_progress("doc-1")
    assert progress["cursor"] == 3
    assert progress["details"]["chunks"] == 5

    diagnostics = store.diagnostics_summary()
    assert diagnostics["total_sessions"] == 1
    assert diagnostics["open_sessions"] == 0
    assert diagnostics["total_events"] == 1
    assert diagnostics["failure_counts"]["FAIL"] == 0
    assert diagnostics["recent_read_documents"][0]["title"] == "notes.md"
