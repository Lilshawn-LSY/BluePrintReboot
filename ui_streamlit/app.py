from pathlib import Path

import pandas as pd
import streamlit as st

from ingest.crossref import (
    CrossrefLookupError,
    check_crossref_connectivity,
    fetch_crossref_by_doi,
    parse_crossref_work,
    proxy_environment,
)
from ingest.doi import is_probable_doi, normalize_doi
from ingest.scanner import extract_doi_metadata_from_pdf
from storage.index_store import (
    INDEX_COLUMNS,
    accept_crossref_metadata,
    load_index,
    update_index_from_scan,
    update_paper_metadata,
)
from storage.note_store import create_note_if_missing, load_note_text, save_note_text
from storage.paths import DATA_DIR, EXPORTS_DIR, INDEX_CSV, NOTES_DIR, PAPERS_DIR, ensure_workspace_dirs


STATUS_OPTIONS = ["unread", "reading", "read"]
READING_PRIORITY_OPTIONS = ["low", "normal", "high"]
LIBRARY_COLUMNS = [
    "title",
    "authors",
    "year",
    "journal",
    "status",
    "reading_priority",
    "tags",
    "metadata_source",
    "filename",
]


def _index() -> pd.DataFrame:
    return load_index()


def _selected_record(df: pd.DataFrame) -> dict[str, str] | None:
    paper_id = st.session_state.get("active_paper_id")
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
    reading_papers = int((df["status"] == "reading").sum()) if not df.empty else 0
    read_papers = int((df["status"] == "read").sum()) if not df.empty else 0
    high_priority_papers = int((df["reading_priority"] == "high").sum()) if not df.empty else 0
    papers_with_doi = int((df["doi"] != "").sum()) if not df.empty else 0
    crossref_papers = int((df["metadata_source"] == "crossref").sum()) if not df.empty else 0
    notes_created = sum(1 for path in NOTES_DIR.glob("*.md")) if NOTES_DIR.exists() else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total papers", total_papers)
    col2.metric("Unread papers", unread_papers)
    col3.metric("Reading papers", reading_papers)
    col4.metric("Read papers", read_papers)
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("High priority", high_priority_papers)
    col6.metric("Papers with DOI", papers_with_doi)
    col7.metric("Crossref metadata", crossref_papers)
    col8.metric("Notes created", notes_created)

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

    col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
    search = col1.text_input("Search")
    status_filter = col2.selectbox("Status", ["all"] + STATUS_OPTIONS)
    priority_filter = col3.selectbox("Priority", ["all"] + READING_PRIORITY_OPTIONS)
    tag_filter = col4.text_input("Tag contains")

    filtered = df.copy()
    if search:
        needle = search.lower()
        search_columns = ["title", "filename", "authors", "journal", "doi", "tags", "metadata_source"]
        search_mask = pd.Series(False, index=filtered.index)
        for column in search_columns:
            search_mask = search_mask | filtered[column].str.lower().str.contains(needle, na=False, regex=False)
        filtered = filtered[search_mask]
    if status_filter != "all":
        filtered = filtered[filtered["status"] == status_filter]
    if priority_filter != "all":
        filtered = filtered[filtered["reading_priority"] == priority_filter]
    if tag_filter:
        filtered = filtered[filtered["tags"].str.lower().str.contains(tag_filter.lower(), na=False, regex=False)]

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
        key="library_selected_paper_id",
    )

    st.dataframe(
        filtered[LIBRARY_COLUMNS],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Open selected paper in Paper Detail"):
        st.session_state["active_paper_id"] = selected
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
    st.write(f"Note path: `{record['note_path']}`")

    st.subheader("Metadata")
    with st.form(key=f"metadata_form_{record['paper_id']}"):
        title = st.text_input("Title", value=record.get("title", ""))
        authors = st.text_input("Authors", value=record.get("authors", ""))
        col1, col2 = st.columns(2)
        year = col1.text_input("Year", value=record.get("year", ""))
        journal = col2.text_input("Journal", value=record.get("journal", ""))
        doi = st.text_input("DOI", value=record.get("doi", ""))
        tags = st.text_input("Tags", value=record.get("tags", ""))

        status_value = record.get("status", "unread")
        if status_value not in STATUS_OPTIONS:
            status_value = "unread"
        priority_value = record.get("reading_priority", "normal")
        if priority_value not in READING_PRIORITY_OPTIONS:
            priority_value = "normal"
        col3, col4 = st.columns(2)
        status = col3.selectbox("Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(status_value))
        reading_priority = col4.selectbox(
            "Reading priority",
            READING_PRIORITY_OPTIONS,
            index=READING_PRIORITY_OPTIONS.index(priority_value),
        )

        save_metadata = st.form_submit_button("Save Metadata")

    if save_metadata:
        update_paper_metadata(
            record["paper_id"],
            {
                "title": title,
                "authors": authors,
                "year": year,
                "journal": journal,
                "doi": doi,
                "tags": tags,
                "status": status,
                "reading_priority": reading_priority,
            },
        )
        st.success("Metadata saved.")
        st.rerun()

    metadata_assist_section(record)

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


def metadata_assist_section(record: dict[str, str]) -> None:
    st.subheader("Metadata Assist")
    current_doi = record.get("doi", "")
    st.write(f"Current DOI: `{current_doi or 'not set'}`")
    preview_key = f"crossref_preview_{record['paper_id']}"
    extraction_key = f"doi_extraction_{record['paper_id']}"

    if st.button("Extract DOI from PDF"):
        result = extract_doi_metadata_from_pdf(Path(record["filepath"]))
        detected_doi = result.doi
        normalized_current_doi = normalize_doi(current_doi)
        saved = False
        message = ""
        if detected_doi and not normalized_current_doi:
            update_paper_metadata(record["paper_id"], {"doi": detected_doi})
            saved = True
            message = "Detected DOI was saved to this paper."
        elif detected_doi and detected_doi == normalized_current_doi:
            message = "Detected DOI already matches the saved DOI."
        elif detected_doi:
            message = "Detected DOI was not saved because this paper already has a DOI."
        else:
            message = "No DOI detected. You can paste one manually."

        st.session_state[extraction_key] = {
            "doi": detected_doi,
            "source": result.source,
            "saved": saved,
            "message": message,
        }
        if saved:
            st.rerun()

    extraction = st.session_state.get(extraction_key)
    if extraction:
        detected_doi = extraction.get("doi", "")
        if detected_doi:
            if extraction.get("saved"):
                st.success(extraction["message"])
            else:
                st.info(extraction["message"])
            st.write(f"Detected DOI: `{detected_doi}`")
            st.write(f"Extraction source: `{extraction.get('source', 'none')}`")
            st.write(f"Saved to index: `{'yes' if extraction.get('saved') else 'no'}`")

            normalized_current_doi = normalize_doi(current_doi)
            if normalized_current_doi and detected_doi != normalized_current_doi:
                if st.button("Replace saved DOI with detected DOI"):
                    update_paper_metadata(record["paper_id"], {"doi": detected_doi})
                    st.session_state[extraction_key]["saved"] = True
                    st.session_state[extraction_key]["message"] = "Detected DOI was saved to this paper."
                    st.success("Saved detected DOI.")
                    st.rerun()

            if st.button("Fetch Crossref metadata for detected DOI"):
                try:
                    message = fetch_crossref_by_doi(detected_doi)
                    st.session_state[preview_key] = parse_crossref_work(message)
                    st.success("Crossref metadata found. Review the preview before accepting it.")
                    st.rerun()
                except CrossrefLookupError as exc:
                    st.warning(str(exc))
                except Exception as exc:
                    st.warning(f"Crossref lookup failed: {exc}")
        else:
            st.info(extraction["message"])

    if st.button("Lookup Crossref by DOI"):
        normalized = normalize_doi(current_doi)
        if not normalized:
            st.warning("Enter and save a DOI before looking up Crossref metadata.")
        elif not is_probable_doi(normalized):
            st.warning("The DOI does not look valid.")
        else:
            try:
                message = fetch_crossref_by_doi(normalized)
                st.session_state[preview_key] = parse_crossref_work(message)
                st.success("Crossref metadata found. Review the preview before accepting it.")
                st.rerun()
            except CrossrefLookupError as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.warning(f"Crossref lookup failed: {exc}")

    preview = st.session_state.get(preview_key)
    if not preview:
        return

    st.write("Crossref preview")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "field": field,
                    "value": preview.get(field, ""),
                }
                for field in (
                    "title",
                    "authors",
                    "year",
                    "journal",
                    "doi",
                    "metadata_source",
                    "metadata_confidence",
                )
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    if st.button("Accept Crossref Metadata"):
        accept_crossref_metadata(record["paper_id"], preview)
        st.session_state.pop(preview_key, None)
        st.success("Crossref metadata accepted.")
        st.rerun()


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
    st.write("Current index schema")
    st.code("\n".join(INDEX_COLUMNS))
    st.subheader("Crossref Connectivity")
    proxy_vars = proxy_environment()
    if proxy_vars:
        st.warning(
            "Proxy environment variables are set: "
            + ", ".join(f"{name}={value}" for name, value in proxy_vars.items())
        )
    if st.button("Test Crossref Connection"):
        result = check_crossref_connectivity()
        if result["ok"]:
            st.success(f"{result['message']} HTTP status: {result['status_code']}")
        else:
            st.warning(
                f"{result['message']} Likely causes include a restricted network, firewall/proxy, "
                "temporary Crossref/API issue, or offline environment."
            )
    st.write(
        "Crossref assist is optional. No API key is required; internet is needed only when you click lookup. "
        "Metadata remains stored locally in data/paper_index.csv."
    )
    st.write("Use v0.3 by entering a DOI in Paper Detail, saving metadata, looking up Crossref, reviewing the preview, and accepting it only if it looks right.")


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
