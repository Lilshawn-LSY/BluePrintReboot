from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import MutableMapping

import streamlit as st
import streamlit.components.v1 as components

from ingest.tag_suggester import merge_tags, normalize_tag, suggest_tags
from storage.index_store import update_paper_metadata
from storage.note_store import load_note_text, save_note_text


STATUS_OPTIONS = ["unread", "reading", "read"]
READING_PRIORITY_OPTIONS = ["low", "normal", "high"]

NOTE_BLOCKS = {
    "summary": "## Summary\n\n- \n",
    "key_claim": "## Key Claim\n\n- Claim: \n- Why it matters: \n",
    "method": "## Method\n\n- Approach: \n- Inputs: \n- Outputs: \n",
    "evidence": "## Evidence\n\n- Evidence: \n- Figure/Table/Page: \n",
    "question": "## Question\n\n- Question: \n- Follow-up: \n",
}


def first_author(record: dict[str, str]) -> str:
    authors = str(record.get("authors", "")).strip()
    if not authors:
        return ""
    first = authors.split(";")[0].split(",")[0].strip()
    return first


def citation_block(record: dict[str, str]) -> str:
    author = first_author(record) or "Unknown author"
    year = str(record.get("year", "")).strip() or "n.d."
    title = str(record.get("title") or record.get("filename") or "Untitled").strip()
    journal = str(record.get("journal", "")).strip()
    doi = str(record.get("doi", "")).strip()
    parts = [f"{author} ({year}). {title}."]
    if journal:
        parts.append(journal + ".")
    if doi:
        parts.append(f"DOI: {doi}.")
    return "## Citation\n\n" + " ".join(parts).strip() + "\n"


def insert_note_block(text: str, block_type: str, record: dict[str, str] | None = None) -> str:
    block = citation_block(record or {}) if block_type == "citation" else NOTE_BLOCKS.get(block_type, "")
    if not block:
        return text
    base = text.rstrip()
    return f"{base}\n\n{block}".lstrip()


def normalize_manual_tag(value: str) -> str:
    return normalize_tag(" ".join(str(value or "").split()))


def add_manual_tag(existing_tags: str, manual_tag: str) -> str:
    tag = normalize_manual_tag(manual_tag)
    if not tag:
        return existing_tags
    return merge_tags(existing_tags, [tag])


def build_metadata_summary(record: dict[str, str]) -> dict[str, str]:
    return {
        "title": str(record.get("title") or record.get("filename") or "Untitled"),
        "first_author": first_author(record),
        "year": str(record.get("year", "")),
        "journal": str(record.get("journal", "")),
        "doi": str(record.get("doi", "")),
        "tags": str(record.get("tags", "")),
        "status": str(record.get("status", "")),
        "reading_priority": str(record.get("reading_priority", "")),
    }


def pdf_path_status(record: dict[str, str]) -> dict[str, object]:
    pdf_path = Path(str(record.get("filepath", "")))
    exists = bool(record.get("filepath")) and pdf_path.exists() and pdf_path.is_file()
    size_mb = round(pdf_path.stat().st_size / (1024 * 1024), 6) if exists else 0.0
    return {
        "path": pdf_path,
        "exists": exists,
        "size_mb": size_mb,
        "message": "" if exists else f"PDF file not found: {pdf_path}",
    }


def note_draft_key(record: dict[str, str]) -> str:
    return f"reader_note_draft_{record['paper_id']}"


def note_saved_at_key(record: dict[str, str]) -> str:
    return f"reader_note_saved_at_{record['paper_id']}"


def load_note_draft(
    record: dict[str, str],
    session_state: MutableMapping,
    notes_dir: Path | None = None,
) -> str:
    key = note_draft_key(record)
    if key not in session_state:
        if notes_dir is None:
            session_state[key] = load_note_text(record)
        else:
            session_state[key] = load_note_text(record, notes_dir=notes_dir)
    return str(session_state[key])


def save_note_draft(
    record: dict[str, str],
    session_state: MutableMapping,
    notes_dir: Path | None = None,
) -> Path:
    text = str(session_state.get(note_draft_key(record), ""))
    if notes_dir is None:
        note_path = save_note_text(record, text)
    else:
        note_path = save_note_text(record, text, notes_dir=notes_dir)
    session_state[note_saved_at_key(record)] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return note_path


def pdf_embed_html(pdf_path: Path, height: int = 900) -> str:
    data = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    return (
        '<object '
        f'data="data:application/pdf;base64,{data}" '
        f'type="application/pdf" width="100%" height="{height}">'
        f'<embed src="data:application/pdf;base64,{data}" '
        f'type="application/pdf" width="100%" height="{height}" />'
        "</object>"
    )


def pdf_rendering_method() -> str:
    return "st.pdf" if hasattr(st, "pdf") else "html-object"


def render_reader_workspace(record: dict[str, str]) -> None:
    st.subheader("Reader Workspace")
    summary = build_metadata_summary(record)
    st.caption(
        " | ".join(
            [
                f"Title: {summary['title']}",
                f"First author: {summary['first_author'] or 'unknown'}",
                f"Year: {summary['year'] or 'n.d.'}",
                f"Journal: {summary['journal'] or 'unknown'}",
                f"DOI: {summary['doi'] or 'not set'}",
                f"Tags: {summary['tags'] or 'none'}",
                f"Status: {summary['status'] or 'unset'}",
                f"Priority: {summary['reading_priority'] or 'unset'}",
            ]
        )
    )

    toolbar_key = f"reader_toolbar_open_{record['paper_id']}"
    if toolbar_key not in st.session_state:
        st.session_state[toolbar_key] = True

    if st.session_state[toolbar_key]:
        toolbar_col, pdf_col, note_col = st.columns([0.9, 2.8, 2.2])
    else:
        toolbar_col, pdf_col, note_col = st.columns([0.2, 3.1, 2.2])

    with toolbar_col:
        _render_toolbar(record, toolbar_key)
    with pdf_col:
        _render_pdf_viewer(record)
    with note_col:
        _render_note_editor(record)


def _render_toolbar(record: dict[str, str], toolbar_key: str) -> None:
    if not st.session_state[toolbar_key]:
        if st.button("Show Toolbar", key=f"show_toolbar_{record['paper_id']}"):
            st.session_state[toolbar_key] = True
            st.rerun()
        return

    if st.button("Hide Toolbar", key=f"hide_toolbar_{record['paper_id']}"):
        st.session_state[toolbar_key] = False
        st.rerun()

    if st.button("Save Note", key=f"toolbar_save_note_{record['paper_id']}"):
        save_note_draft(record, st.session_state)
        st.success("Note saved.")

    if st.button("Reload Note", key=f"toolbar_reload_note_{record['paper_id']}"):
        st.session_state[note_draft_key(record)] = load_note_text(record)
        st.info("Note reloaded from disk.")
        st.rerun()

    for label, block_type in (
        ("Insert Summary block", "summary"),
        ("Insert Key Claim block", "key_claim"),
        ("Insert Method block", "method"),
        ("Insert Evidence block", "evidence"),
        ("Insert Question block", "question"),
        ("Insert Citation block", "citation"),
    ):
        if st.button(label, key=f"{block_type}_{record['paper_id']}"):
            key = note_draft_key(record)
            current = load_note_draft(record, st.session_state)
            st.session_state[key] = insert_note_block(current, block_type, record)
            st.rerun()

    manual_tag = st.text_input("Manual tag", key=f"manual_tag_{record['paper_id']}")
    if st.button("Add manual tag", key=f"add_manual_tag_{record['paper_id']}"):
        updated_tags = add_manual_tag(str(record.get("tags", "")), manual_tag)
        if updated_tags != str(record.get("tags", "")):
            update_payload = {"tags": updated_tags}
            update_paper_metadata(record["paper_id"], update_payload)
            st.success("Tag added.")
            st.rerun()
        else:
            st.info("No tag added.")

    if st.button("Run tag suggestions", key=f"reader_suggest_tags_{record['paper_id']}"):
        suggestions = suggest_tags(record)
        if suggestions:
            updated_tags = merge_tags(str(record.get("tags", "")), suggestions)
            update_paper_metadata(record["paper_id"], {"tags": updated_tags})
            st.success("Suggested tags added.")
            st.rerun()
        else:
            st.info("No new suggested tags.")

    current_status = record.get("status", "unread")
    if current_status not in STATUS_OPTIONS:
        current_status = "unread"
    selected_status = st.selectbox(
        "Reading status",
        STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(current_status),
        key=f"reader_status_{record['paper_id']}",
    )
    if selected_status != record.get("status", ""):
        update_paper_metadata(record["paper_id"], {"status": selected_status})
        st.rerun()

    current_priority = record.get("reading_priority", "normal")
    if current_priority not in READING_PRIORITY_OPTIONS:
        current_priority = "normal"
    selected_priority = st.selectbox(
        "Reading priority",
        READING_PRIORITY_OPTIONS,
        index=READING_PRIORITY_OPTIONS.index(current_priority),
        key=f"reader_priority_{record['paper_id']}",
    )
    if selected_priority != record.get("reading_priority", ""):
        update_paper_metadata(record["paper_id"], {"reading_priority": selected_priority})
        st.rerun()


def _render_pdf_viewer(record: dict[str, str]) -> None:
    st.write("PDF")
    status = pdf_path_status(record)
    method = pdf_rendering_method()
    with st.expander("PDF debug"):
        st.write(f"PDF path: `{status['path']}`")
        st.write(f"Exists: `{status['exists']}`")
        st.write(f"File size MB: `{status['size_mb']}`")
        st.write(f"Rendering method: `{method}`")
    if not status["exists"]:
        st.warning(str(status["message"]))
        return
    if method == "st.pdf":
        st.pdf(str(status["path"]), height=920)
    else:
        components.html(pdf_embed_html(status["path"], height=920), height=940, scrolling=True)


def _render_note_editor(record: dict[str, str]) -> None:
    st.write("Markdown Note")
    key = note_draft_key(record)
    load_note_draft(record, st.session_state)
    st.text_area(
        "Note draft",
        height=860,
        key=key,
    )
    if st.button("Save Note", key=f"editor_save_note_{record['paper_id']}"):
        save_note_draft(record, st.session_state)
        st.success("Note saved.")
    if st.button("Reload Note", key=f"editor_reload_note_{record['paper_id']}"):
        st.session_state[key] = load_note_text(record)
        st.rerun()
    saved_at = st.session_state.get(note_saved_at_key(record), "")
    if saved_at:
        st.caption(f"Last saved: {saved_at}")
