from ui_streamlit.app import navigation_pages, run


def test_streamlit_entrypoint_is_callable() -> None:
    assert callable(run)


def test_navigation_pages_are_clear_and_logically_ordered() -> None:
    assert list(navigation_pages()) == [
        "Dashboard",
        "Library",
        "Paper Detail",
        "Project Workspace",
        "Tag Manager",
        "Settings",
    ]
