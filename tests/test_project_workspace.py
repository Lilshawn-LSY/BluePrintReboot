from ui_streamlit.project_workspace import (
    PROJECT_LINK_EDIT_KEY,
    clear_project_link_action_state,
    open_paper_in_reader,
    project_link_counts,
    project_link_unlink_confirmation_key,
)


def test_project_link_counts_separates_papers_and_note_blocks() -> None:
    links = [
        {"project_id": "project-1", "target_type": "paper"},
        {"project_id": "project-1", "target_type": "note_block"},
        {"project_id": "project-1", "target_type": "note_block"},
        {"project_id": "project-2", "target_type": "paper"},
    ]

    assert project_link_counts("project-1", links) == {"paper": 1, "note_block": 2}


def test_open_paper_in_reader_uses_existing_navigation_state() -> None:
    session_state = {"current_page": "Project Workspace"}

    open_paper_in_reader("paper-1", session_state)

    assert session_state["active_paper_id"] == "paper-1"
    assert session_state["current_page"] == "Paper Detail"


def test_clear_project_link_action_state_clears_edit_and_unlink_confirmation() -> None:
    confirmation = project_link_unlink_confirmation_key("link-1")
    session_state = {
        PROJECT_LINK_EDIT_KEY: "link-1",
        confirmation: True,
        "unrelated": "keep",
    }

    clear_project_link_action_state(session_state, "link-1")

    assert PROJECT_LINK_EDIT_KEY not in session_state
    assert confirmation not in session_state
    assert session_state["unrelated"] == "keep"


def test_clearing_another_link_does_not_close_active_edit() -> None:
    session_state = {PROJECT_LINK_EDIT_KEY: "link-2"}

    clear_project_link_action_state(session_state, "link-1")

    assert session_state[PROJECT_LINK_EDIT_KEY] == "link-2"
