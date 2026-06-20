from ui_streamlit.project_workspace import open_paper_in_reader, project_link_counts


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
