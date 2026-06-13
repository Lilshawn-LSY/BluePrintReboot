from ui_streamlit.app import run


def test_streamlit_entrypoint_is_callable() -> None:
    assert callable(run)
