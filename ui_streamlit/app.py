import pandas as pd
import streamlit as st

from storage.index_store import load_index, update_index_from_scan, update_paper_status
from storage.note_store import create_note_if_missing, load_note_text, save_note_text
from storage.paths import DATA_DIR, EXPORTS_DIR, INDEX_CSV, NOTES_DIR, PAPERS_DIR, ensure_workspace_dirs


STATUSES = ["unread", "reading", "read", "missing"]


def _index() -> pd.DataFrame:
    return load_index()


def _selected_record(df: pd.DataFrame) -> dict[str, str] | None:
    paper_id = st.session_state.get("selected_paper_id")
    if not paper_id or df.empty:
        return None
    matches = df[df["paper_id"] == paper_id]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


def _scan_button(key: str) -> None:
    if st.button("Scan papers", key=key):
        update_index_from_scan()
        st.success("Paper index updated.")
        st.rerun()


def dashboard_page() -> None:
    st.title("BluePrintReboot")
    df = _index()

    total_papers = len(df)
    unread_papers = int((df["status"] == "unread").sum()) if not df.empty else 0
    notes_created = sum(1 for path in NOTES_DIR.glob("*.md")) if NOTES_DIR.exists() else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total papers", total_papers)
    col2.metric("Unread papers", unread_papers)
    col3.metric("Notes created", notes_created)

    _scan_button("dashboard_scan")

    st.subheader("Recent papers")
    if df.empty:
        st.info("No papers indexed yet. Add PDF files to papers/ and scan.")
    else:
        recent = df.sort_values("added_at", ascending=False).head(5)
        st.dataframe(recent[["title", "filename", "status", "added_at"]], use_container_width=True, hide_index=True)


def library_page() -> None:
    st.title("Library")
    df = _index()

    col1, col2 = st.columns([3, 1])
    search = col1.text_input("Search by title or filename")
    status_filter = col2.selectbox("Status", ["all"] + STATUSES)

    filtered = df.copy()
    if search:
        needle = search.lower()
        filtered = filtered[
            filtered["title"].str.lower().str.contains(needle, na=False)
            | filtered["filename"].str.lower().str.contains(needle, na=False)
        ]
    if status_filter != "all":
        filtered = filtered[filtered["status"] == status_filter]

    if filtered.empty:
        st.info("No matching papers.")
        _scan_button("library_scan")
        return

    labels = {
        row.paper_id: f"{row.title} ({row.filename})"
        for row in filtered.itertuples(index=False)
    }
    selected = st.selectbox(
        "Select paper",
        options=list(labels.keys()),
        format_func=lambda paper_id: labels.get(paper_id, paper_id),
        index=0,
    )
    st.session_state["selected_paper_id"] = selected

    st.dataframe(
        filtered[["title", "filename", "status", "filepath"]],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Open selected paper in Paper Detail"):
        st.session_state["selected_paper_id"] = selected
        st.session_state["current_page"] = "Paper Detail"
        st.rerun()


def paper_detail_page() -> None:
    st.title("Paper Detail")
    df = _index()
    record = _selected_record(df)
    if record is None:
        st.info("Select a paper from Library first.")
        return

    st.subheader(record["title"])
    st.write(f"Filename: `{record['filename']}`")
    st.write(f"Filepath: `{record['filepath']}`")

    status_index = STATUSES.index(record["status"]) if record["status"] in STATUSES else 0
    status = st.selectbox("Status", STATUSES, index=status_index)
    if status != record["status"]:
        update_paper_status(record["paper_id"], status)
        record["status"] = status
        st.success("Status saved.")

    if st.button("Create/Open Note"):
        create_note_if_missing(record)
        st.session_state[f"note_open_{record['paper_id']}"] = True
        st.rerun()

    note_path = NOTES_DIR / f"{record['paper_id']}.md"
    note_is_open = st.session_state.get(f"note_open_{record['paper_id']}", note_path.exists())
    if note_is_open:
        text = load_note_text(record)
        edited = st.text_area("Note", value=text, height=520, key=f"note_text_{record['paper_id']}")
        if st.button("Save Note"):
            save_note_text(record, edited)
            st.success("Note saved.")
        st.caption(f"Note path: {note_path}")


def settings_page() -> None:
    st.title("Settings")
    st.write("Resolved local workspace paths")
    st.code(
        "\n".join(
            [
                f"data: {DATA_DIR}",
                f"papers: {PAPERS_DIR}",
                f"notes: {NOTES_DIR}",
                f"exports: {EXPORTS_DIR}",
                f"index csv: {INDEX_CSV}",
            ]
        )
    )
    st.write("Use v0.1 by placing PDFs in papers/, scanning, selecting a paper in Library, and editing its Markdown note in Paper Detail.")


def run() -> None:
    ensure_workspace_dirs()
    st.set_page_config(page_title="BluePrintReboot", layout="wide")

    pages = {
        "Dashboard": dashboard_page,
        "Library": library_page,
        "Paper Detail": paper_detail_page,
        "Settings": settings_page,
    }
    page_names = list(pages.keys())
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Dashboard"

    current_page = st.session_state["current_page"]
    if current_page not in page_names:
        current_page = "Dashboard"
        st.session_state["current_page"] = current_page

    nav_choice = st.sidebar.radio(
        "Navigation",
        page_names,
        index=page_names.index(current_page),
    )
    if nav_choice != st.session_state["current_page"]:
        st.session_state["current_page"] = nav_choice
        st.rerun()

    pages[st.session_state["current_page"]]()
