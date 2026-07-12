from streamlit.testing.v1 import AppTest

from services.reading_note_template import render_reading_note_template
from tests.helpers import make_workspace


def test_reader_save_updates_widget_state_only_on_pre_widget_rerun() -> None:
    root = make_workspace("reader-save-apptest")
    notes = root / "notes"
    notes.mkdir()
    old_record = {"paper_id": "paper-a", "title": "Paper", "tags": "old"}
    note_path = notes / "paper-a.md"
    note_path.write_text(render_reading_note_template(old_record) + "Original body\n", encoding="utf-8")
    script = f'''
from pathlib import Path
import streamlit as st
from ui_streamlit.reader_workspace import apply_pending_note_actions, note_draft_key, reader_note_status, save_note_draft

record = {{"paper_id": "paper-a", "title": "Paper", "tags": "latest"}}
notes_dir = Path({str(notes)!r})
apply_pending_note_actions(record, st.session_state, notes_dir=notes_dir)
st.text_area("Paper Reading Note", key=note_draft_key(record))
if st.button("Save note"):
    try:
        save_note_draft(record, st.session_state, notes_dir=notes_dir)
    except (OSError, ValueError) as exc:
        st.error(f"save failed: {{exc}}")
    else:
        st.rerun()
state = reader_note_status(record, st.session_state)
st.write(f"dirty={{state.dirty}}")
'''
    app = AppTest.from_string(script).run()
    edited = app.text_area[0].value.replace("Original body", "Latest user-edited body")
    app.text_area[0].set_value(edited).run()

    app.button[0].click().run()

    assert not app.exception
    assert "tags: latest" in app.text_area[0].value
    assert "Latest user-edited body" in app.text_area[0].value
    assert any("dirty=False" in item.value for item in app.markdown)
    saved = note_path.read_text(encoding="utf-8")
    assert "tags: latest" in saved
    assert "Latest user-edited body" in saved
