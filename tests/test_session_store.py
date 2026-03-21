from pathlib import Path

from app.session_store import ChatSessionStore


def test_session_store_creates_and_reads_messages(tmp_path: Path):
    store = ChatSessionStore(tmp_path / "chatbot.sqlite3")
    session = store.create_session(
        user_id=7,
        username="sara",
        user_label="Sara",
        roles=["AVOCAT"],
        title="Assistant IA - AVOCAT",
        page_id="avocatdashboardpage",
        current_path="/dashboard/avocat",
    )

    store.add_message(session.session_id, "assistant", "Bonjour")
    store.add_message(session.session_id, "user", "Aide-moi")
    store.set_last_response_id(session.session_id, "resp_123")

    fetched = store.get_session(session.session_id)
    messages = store.list_messages(session.session_id)

    assert fetched is not None
    assert fetched.last_response_id == "resp_123"
    assert [message.role for message in messages] == ["assistant", "user"]
