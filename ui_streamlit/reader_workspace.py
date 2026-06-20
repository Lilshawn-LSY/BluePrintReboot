from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import MutableMapping

import streamlit as st
import streamlit.components.v1 as components

from ingest.tag_suggester import merge_tags, normalize_tag, suggest_tags
from ingest.text_extractor import extraction_diagnostics
from services.full_text_workflow import clear_text_cache_for_paper, extract_text_for_paper
from storage.extracted_text_store import (
    extraction_cache_status,
    load_cached_extracted_text,
)
from storage.index_store import update_paper_metadata
from storage.note_block_store import (
    ALLOWED_BLOCK_TYPES,
    create_note_block,
    delete_note_block,
    list_note_blocks,
    render_note_block_as_markdown,
    update_note_block,
)
from storage.note_store import load_note_text, save_note_text
from ui_streamlit.project_workspace import render_note_block_project_links


STATUS_OPTIONS = ["unread", "reading", "read"]
READING_PRIORITY_OPTIONS = ["low", "normal", "high"]
STABLE_HTML_RENDERER = "Stable HTML viewer"
NATIVE_STREAMLIT_RENDERER = "Native Streamlit PDF viewer"
PDF_RENDERER_OPTIONS = [STABLE_HTML_RENDERER, NATIVE_STREAMLIT_RENDERER]

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


def structured_note_edit_key(record: dict[str, str]) -> str:
    return f"structured_note_edit_id_{record['paper_id']}"


def pending_note_block_append_key(record: dict[str, str]) -> str:
    return f"pending_note_block_append_{record['paper_id']}"


def pending_note_reload_key(record: dict[str, str]) -> str:
    return f"pending_note_reload_{record['paper_id']}"


def append_markdown_snapshot(markdown: str, snippet: str) -> str:
    existing = str(markdown or "").rstrip()
    snapshot = str(snippet or "").strip()
    if not snapshot:
        return str(markdown or "")
    if not existing:
        return f"{snapshot}\n"
    return f"{existing}\n\n{snapshot}\n"


def apply_pending_note_actions(
    record: dict[str, str],
    session_state: MutableMapping,
    notes_dir: Path | None = None,
) -> str:
    key = note_draft_key(record)
    draft = load_note_draft(record, session_state, notes_dir=notes_dir)

    if session_state.pop(pending_note_reload_key(record), False):
        if notes_dir is None:
            draft = load_note_text(record)
        else:
            draft = load_note_text(record, notes_dir=notes_dir)
        session_state[key] = draft

    pending_snapshot = str(session_state.pop(pending_note_block_append_key(record), "") or "")
    if pending_snapshot:
        draft = append_markdown_snapshot(draft, pending_snapshot)
        session_state[key] = draft

    return str(session_state[key])


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


def native_pdf_support_status() -> dict[str, object]:
    try:
        __import__("streamlit_pdf")
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    return {"available": True, "error": ""}


def initial_pdf_render_status(
    selected_renderer: str = STABLE_HTML_RENDERER,
    native_status: dict[str, object] | None = None,
) -> dict[str, object]:
    support = native_status if native_status is not None else native_pdf_support_status()
    return {
        "selected_renderer": selected_renderer,
        "native_available": bool(support.get("available", False)),
        "native_availability_error": str(support.get("error", "")),
        "attempted_methods": [],
        "final_method": "",
        "native_render_error": "",
    }


def mark_pdf_render_fallback(status: dict[str, object], error: Exception | str | None = None) -> dict[str, object]:
    updated = dict(status)
    attempted = list(updated.get("attempted_methods", []))
    if "html-object" not in attempted:
        attempted.append("html-object")
    updated["attempted_methods"] = attempted
    updated["final_method"] = "html-object"
    if error:
        updated["native_render_error"] = str(error)
    return updated


def mark_pdf_render_native_attempt(status: dict[str, object]) -> dict[str, object]:
    updated = dict(status)
    attempted = list(updated.get("attempted_methods", []))
    if "st.pdf" not in attempted:
        attempted.append("st.pdf")
    updated["attempted_methods"] = attempted
    return updated


def mark_pdf_render_native_success(status: dict[str, object]) -> dict[str, object]:
    updated = mark_pdf_render_native_attempt(status)
    updated["final_method"] = "st.pdf"
    return updated


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
        _render_structured_note_blocks(record)


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
        st.session_state[pending_note_reload_key(record)] = True
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
    selected_renderer = st.selectbox(
        "PDF renderer",
        PDF_RENDERER_OPTIONS,
        index=0,
        key=f"pdf_renderer_{record['paper_id']}",
    )
    if not status["exists"]:
        render_status = initial_pdf_render_status(selected_renderer)
        _render_pdf_debug(status, render_status)
        st.warning(str(status["message"]))
        _render_extracted_text_panel(record, status)
        return

    render_status = initial_pdf_render_status(selected_renderer)
    if selected_renderer == NATIVE_STREAMLIT_RENDERER:
        try:
            render_status = mark_pdf_render_native_attempt(render_status)
            st.pdf(str(status["path"]), height=920)
            render_status = mark_pdf_render_native_success(render_status)
        except Exception as exc:
            st.warning("Native PDF viewer failed. Falling back to stable HTML viewer.")
            render_status = mark_pdf_render_fallback(render_status, exc)
            components.html(pdf_embed_html(status["path"], height=920), height=940, scrolling=True)
    else:
        render_status = mark_pdf_render_fallback(render_status)
        components.html(pdf_embed_html(status["path"], height=920), height=940, scrolling=True)
    _render_pdf_debug(status, render_status)
    _render_extracted_text_panel(record, status)


def _render_pdf_debug(path_status: dict[str, object], render_status: dict[str, object]) -> None:
    with st.expander("PDF debug"):
        st.write(f"PDF path: `{path_status['path']}`")
        st.write(f"Exists: `{path_status['exists']}`")
        st.write(f"File size MB: `{path_status['size_mb']}`")
        st.write(f"Selected renderer: `{render_status['selected_renderer']}`")
        st.write(f"Native PDF support available: `{render_status['native_available']}`")
        if render_status.get("native_availability_error"):
            st.write(f"Native availability error: `{render_status['native_availability_error']}`")
        st.write(f"Attempted render methods: `{', '.join(render_status['attempted_methods'])}`")
        st.write(f"Final render method: `{render_status['final_method']}`")
        if render_status.get("native_render_error"):
            st.write(f"Native render error: `{render_status['native_render_error']}`")


def _render_extracted_text_panel(record: dict[str, str], pdf_status: dict[str, object]) -> None:
    paper_id = record["paper_id"]
    cache_status = extraction_cache_status(paper_id, pdf_path=pdf_status["path"])
    show_key = f"show_extracted_text_{paper_id}"

    col1, col2, col3, col4 = st.columns(4)
    if col1.button("Extract full text", key=f"extract_text_{paper_id}"):
        _run_full_text_extraction(record, force=False)
        st.session_state[show_key] = True
        st.rerun()
    if col2.button("Re-extract full text", key=f"reextract_text_{paper_id}"):
        _run_full_text_extraction(record, force=True)
        st.session_state[show_key] = True
        st.rerun()
    if col3.button("Show extracted text", key=f"show_text_{paper_id}"):
        st.session_state[show_key] = not st.session_state.get(show_key, False)
    if col4.button("Clear text cache", key=f"clear_text_{paper_id}"):
        clear_text_cache_for_paper(record)
        st.session_state[show_key] = False
        st.rerun()

    st.caption(
        " | ".join(
            [
                f"text status: {cache_status['status']}",
                f"source: {cache_status['source'] or 'none'}",
                f"chars: {cache_status['char_count']}",
                f"extracted: {cache_status['extracted_at'] or 'never'}",
            ]
        )
    )

    if cache_status["recovery_failed"] and cache_status["previous_cache_preserved"]:
        message = "Re-extraction failed, so the previous extracted text was preserved."
        if cache_status["is_stale"]:
            message += " The PDF changed, so the preserved cache may still be stale."
        st.warning(message)
    elif cache_status["is_stale"]:
        st.warning(
            "The PDF changed since full text was last extracted, so the cache may be stale. "
            "Click Extract full text to refresh it."
        )
    elif cache_status["has_reusable_text_cache"]:
        st.success("The full-text cache is reusable for this PDF.")
    elif not cache_status["has_text_file"] and not cache_status["has_metadata_file"]:
        st.info("No full-text cache yet. Click Extract full text to create one.")
    elif cache_status["error"]:
        st.warning(f"No reusable full-text cache is available. Last extraction error: {cache_status['error']}")
    else:
        st.info("No reusable full-text cache is available. Click Extract full text to try again.")

    with st.expander("Extraction debug"):
        diagnostics = extraction_diagnostics(pdf_status["path"])
        st.write(f"PDF path: `{diagnostics['pdf_path']}`")
        st.write(f"PDF exists: `{diagnostics['pdf_exists']}`")
        st.write(f"PDF size MB: `{diagnostics['pdf_size_mb']}`")
        st.write(f"MarkItDown availability: `{diagnostics['markitdown']}`")
        st.write(f"pypdf availability: `{diagnostics['pypdf']}`")
        st.write(f"Attempted extraction methods: `{', '.join(cache_status['attempted_methods'])}`")
        st.write(f"Final source: `{cache_status['source'] or 'none'}`")
        st.write(f"Character count: `{cache_status['char_count']}`")
        st.write(f"Cache stale: `{cache_status['is_stale']}`")
        st.write(f"Previous cache preserved: `{cache_status['previous_cache_preserved']}`")
        st.write(f"Recovery failed: `{cache_status['recovery_failed']}`")
        if cache_status["recovery_attempted_at"]:
            st.write(f"Recovery attempted: `{cache_status['recovery_attempted_at']}`")
        st.write(f"Current PDF SHA-256: `{cache_status['pdf_sha256'] or 'unavailable'}`")
        st.write(f"Cached PDF SHA-256: `{cache_status['cached_pdf_sha256'] or 'unavailable'}`")
        if cache_status["errors"]:
            label = "Fallback warnings" if cache_status["status"] == "success" else "Errors"
            st.write(f"{label}:")
            for error in cache_status["errors"]:
                st.write(f"- {error}")
        else:
            st.write("Errors: `none`")

    if st.session_state.get(show_key, False):
        text = load_cached_extracted_text(paper_id)
        with st.expander("Extracted Text Preview", expanded=True):
            if text:
                preview = text[:5000]
                st.text_area("Cached extracted text", value=preview, height=320)
                if len(text) > len(preview):
                    st.caption(f"Showing first {len(preview)} of {len(text)} characters.")
                with st.expander("View more extracted text"):
                    st.text_area("Full cached extracted text", value=text, height=600)
            else:
                st.info("No extracted text cache found. Click Extract full text.")


def _run_full_text_extraction(record: dict[str, str], force: bool = False) -> None:
    extract_text_for_paper(record, force=force)


def _render_note_editor(record: dict[str, str]) -> None:
    st.write("Markdown Note")
    key = note_draft_key(record)
    apply_pending_note_actions(record, st.session_state)
    st.text_area(
        "Note draft",
        height=860,
        key=key,
    )
    if st.button("Save Note", key=f"editor_save_note_{record['paper_id']}"):
        save_note_draft(record, st.session_state)
        st.success("Note saved.")
    if st.button("Reload Note", key=f"editor_reload_note_{record['paper_id']}"):
        st.session_state[pending_note_reload_key(record)] = True
        st.rerun()
    saved_at = st.session_state.get(note_saved_at_key(record), "")
    if saved_at:
        st.caption(f"Last saved: {saved_at}")


def _render_structured_note_blocks(record: dict[str, str]) -> None:
    paper_id = record["paper_id"]
    edit_key = structured_note_edit_key(record)
    with st.container(border=True):
        st.write("Structured Note Blocks")
        blocks = list_note_blocks(paper_id)
        type_counts = {
            block_type: sum(block["block_type"] == block_type for block in blocks)
            for block_type in ALLOWED_BLOCK_TYPES
        }
        st.caption(f"Total blocks: {len(blocks)}")
        st.caption(
            "By type: "
            + " | ".join(f"{block_type}: {type_counts[block_type]}" for block_type in ALLOWED_BLOCK_TYPES)
        )
        selected_type = st.selectbox(
            "Filter by block type",
            ("all",) + ALLOWED_BLOCK_TYPES,
            key=f"structured_note_filter_{paper_id}",
        )
        st.caption(
            "Markdown notes remain freeform. Appending a block creates a one-way snapshot in the current draft; "
            "later block edits are not synchronized."
        )

        if not blocks:
            st.info("No structured note blocks yet.")
        else:
            active_edit_id = str(st.session_state.get(edit_key, ""))
            filtered_blocks = [
                block
                for block in blocks
                if selected_type == "all"
                or block["block_type"] == selected_type
                or str(block["id"]) == active_edit_id
            ]
            if not filtered_blocks:
                st.info(f"No {selected_type} blocks.")
            for block in filtered_blocks:
                _render_structured_note_block_card(record, block, edit_key)

        if not st.session_state.get(edit_key):
            _render_create_note_block_form(paper_id)


def _render_structured_note_block_card(
    record: dict[str, str],
    block: dict[str, object],
    edit_key: str,
) -> None:
    paper_id = record["paper_id"]
    block_id = str(block["id"])
    with st.container(border=True):
        heading = str(block["title"] or str(block["block_type"]).replace("_", " ").title())
        st.markdown(f"**{heading}** - `{block['block_type']}`")
        details = [
            value
            for value in (
                f"Page: {block['page']}" if block["page"] else "",
                f"Figure: {block['figure']}" if block["figure"] else "",
                f"Tags: {', '.join(block['tags'])}" if block["tags"] else "",
                f"Updated: {block['updated_at']}",
            )
            if value
        ]
        st.caption(" | ".join(details))

        text = str(block["text"] or "")
        if text:
            preview = _note_block_preview(text)
            st.write(preview)
            if preview != text.strip():
                with st.expander("View full text"):
                    st.write(text)
        if block["quote"]:
            st.caption(f"Quote: {block['quote']}")

        edit_col, append_col, delete_col = st.columns(3)
        if edit_col.button("Edit", key=f"edit_note_block_{paper_id}_{block_id}"):
            st.session_state[edit_key] = block_id
            st.rerun()
        if append_col.button("Append to Markdown", key=f"append_note_block_{paper_id}_{block_id}"):
            st.session_state[pending_note_block_append_key(record)] = render_note_block_as_markdown(block)
            st.rerun()
        if delete_col.button("Delete block", key=f"delete_note_block_{paper_id}_{block_id}"):
            delete_note_block(paper_id, block_id)
            if st.session_state.get(edit_key) == block_id:
                st.session_state.pop(edit_key, None)
            st.rerun()

        if st.session_state.get(edit_key) == block_id:
            _render_edit_note_block_form(paper_id, block, edit_key)

        render_note_block_project_links(record, block)


def _render_edit_note_block_form(
    paper_id: str,
    block: dict[str, object],
    edit_key: str,
) -> None:
    block_id = str(block["id"])
    block_type = str(block["block_type"])
    with st.form(key=f"edit_note_block_form_{paper_id}_{block_id}"):
        st.write("Edit structured block")
        edited_type = st.selectbox(
            "Block type",
            ALLOWED_BLOCK_TYPES,
            index=ALLOWED_BLOCK_TYPES.index(block_type),
            key=f"edit_block_type_{block_id}",
        )
        edited_title = st.text_input("Block title", value=str(block["title"]))
        edited_text = st.text_area("Block text", value=str(block["text"]), height=180)
        page_col, figure_col = st.columns(2)
        edited_page = page_col.text_input("Page", value=str(block["page"]))
        edited_figure = figure_col.text_input("Figure", value=str(block["figure"]))
        edited_quote = st.text_area("Quote", value=str(block["quote"]), height=100)
        edited_tags = st.text_input("Tags (comma-separated)", value=", ".join(block["tags"]))
        save_changes = st.form_submit_button("Save changes")
        cancel_edit = st.form_submit_button("Cancel")

    if cancel_edit:
        st.session_state.pop(edit_key, None)
        st.rerun()
    if save_changes:
        update_note_block(
            paper_id,
            block_id,
            {
                "block_type": edited_type,
                "title": edited_title,
                "text": edited_text,
                "page": edited_page,
                "figure": edited_figure,
                "quote": edited_quote,
                "tags": edited_tags,
            },
        )
        st.session_state.pop(edit_key, None)
        st.rerun()


def _render_create_note_block_form(paper_id: str) -> None:
    with st.form(key=f"create_note_block_{paper_id}"):
        st.write("Add structured block")
        block_type = st.selectbox("Block type", ALLOWED_BLOCK_TYPES)
        title = st.text_input("Block title")
        text = st.text_area("Block text", height=140)
        page_col, figure_col = st.columns(2)
        page = page_col.text_input("Page")
        figure = figure_col.text_input("Figure")
        quote = st.text_area("Quote", height=100)
        tags = st.text_input("Tags (comma-separated)")
        submitted = st.form_submit_button("Add block")

    if submitted:
        create_note_block(
            paper_id=paper_id,
            block_type=block_type,
            title=title,
            text=text,
            page=page,
            figure=figure,
            quote=quote,
            tags=tags,
        )
        st.success("Structured note block added.")
        st.rerun()


def _note_block_preview(text: str, max_length: int = 280) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3].rstrip() + "..."
