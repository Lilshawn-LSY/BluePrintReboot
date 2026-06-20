from ui_streamlit.ui_helpers import (
    clear_session_keys,
    confirmation_key,
    confirmation_pending,
    request_confirmation,
)


def test_confirmation_helpers_require_an_explicit_request_and_clear_cleanly() -> None:
    session_state = {"unrelated": "keep"}
    key = confirmation_key("delete project", "project 1")

    assert key == "ui_confirm_delete_project_project_1"
    assert confirmation_pending(session_state, key) is False

    request_confirmation(session_state, key)
    assert confirmation_pending(session_state, key) is True

    clear_session_keys(session_state, key)
    assert confirmation_pending(session_state, key) is False
    assert session_state["unrelated"] == "keep"
