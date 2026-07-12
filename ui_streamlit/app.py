import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd
import streamlit as st

from config.contact import APP_VERSION
from config.inbox import get_inbox_path
from ingest.crossref import (
    CrossrefLookupError,
    check_crossref_connectivity,
    crossref_dependency_versions,
    lookup_crossref_metadata,
    proxy_environment,
)
from ingest.document_text import get_text_extraction_backends
from ingest.doi import is_probable_doi, normalize_doi
from ingest.tag_suggester import (
    DEFAULT_CANONICAL_TAG_PATH,
    DEFAULT_RULE_PATH,
    audit_canonical_tags,
    build_tag_suggestion_record,
    explain_tag_suggestions,
    load_canonical_tags,
    load_tag_rules,
    merge_tags,
    validate_tag_rules,
)
from services.tag_book import (
    DEFAULT_TAG_BOOK_DIR,
    group_suggestions_by_category,
    load_tag_book,
    preview_near_duplicate_tags,
    selected_suggestion_tag_values,
    suggestion_selection_id,
    validate_tag_book,
)
from services.paper_file_hygiene import (
    PaperFileHygieneError,
    apply_paper_file_rename,
    build_rename_plan,
)
from storage.paper_profile_store import load_profile
from services.backup_snapshot import create_backup_snapshot
from services.storage_recovery import StorageRecoveryError, export_recovery_copy, quarantine_file, restore_quarantined_file
from services.lifecycle_decisions import ignore_exact_duplicate, unignore_exact_duplicate
from services.library_health import (
    ORPHAN_PRESERVE_ACTION,
    ORPHAN_EXPORT_ACTION,
    OrphanRepairError,
    OrphanProjectLinkRepairError,
    build_orphan_note_block_repair_plan,
    build_orphan_note_repair_plan,
    build_orphan_project_link_removal_plan,
    build_orphan_project_link_reattach_plan,
    delete_orphan_note,
    delete_orphan_note_blocks,
    export_orphan_note,
    export_orphan_note_blocks,
    export_orphan_project_link,
    reattach_orphan_note,
    reattach_orphan_note_blocks,
    reattach_orphan_project_link,
    run_library_health_check,
    unlink_orphan_project_link,
)
from services.metadata_fallback import (
    apply_metadata_candidate_to_index,
    build_doi_less_metadata_candidate,
    build_metadata_candidate_update,
    fill_metadata_gaps_from_pdf_profile,
)
from services.missing_pdf_repair import (
    MissingPDFRepairError,
    build_reconnect_plan,
    list_reconnect_candidates,
    reconnect_missing_pdf,
    remove_missing_pdf_from_index,
)
from services.file_lifecycle import (
    FileLifecycleRepairError,
    build_duplicate_reconnect_plan,
    build_duplicate_remove_plan,
    reconnect_duplicate_pdf,
    remove_duplicate_index_row,
)
from services.pdf_inbox import (
    PDFInboxError,
    build_inbox_import_plan,
    import_pdf_from_inbox,
    scan_pdf_inbox,
)
from services.reading_note_template import refresh_reading_note_header
from services.paper_text_profile_builder import build_paper_text_profile
from storage.atomic_json import JsonStoreError
from storage.index_store import (
    INDEX_COLUMNS,
    accept_crossref_metadata,
    enrich_paper_doi_from_pdf,
    load_index,
    filter_archived,
    set_paper_archived,
    update_index_from_scan,
    update_paper_metadata,
)
from storage.note_store import refresh_note_header
from storage.paths import DATA_DIR, EXPORTS_DIR, INDEX_CSV, NOTES_DIR, PAPERS_DIR, PROJECT_ROOT, RECOVERY_DIR, QUARANTINE_DIR, LIFECYCLE_DECISIONS_JSON, ensure_workspace_dirs
from ui_streamlit.project_workspace import render_paper_project_links, render_project_workspace
from ui_streamlit.reader_workspace import (
    has_unsaved_note_changes,
    note_draft_key,
    pending_note_reload_key,
    preserve_reader_context_for_paper_id,
    queue_note_header_refresh,
    render_reader_workspace,
)
from ui_streamlit.tag_manager import render_tag_manager_page


STATUS_OPTIONS = ["unread", "reading", "read"]
READING_PRIORITY_OPTIONS = ["low", "normal", "high"]
LIBRARY_COLUMNS = [
    "title",
    "authors",
    "year",
    "journal",
    "abstract",
    "keywords",
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


def _latest_record_for_paper(paper_id: str) -> dict[str, str] | None:
    df = load_index()
    if df.empty or "paper_id" not in df.columns:
        return None
    matches = df[df["paper_id"] == paper_id]
    if matches.empty:
        return None
    return {str(key): str(value) for key, value in matches.iloc[0].fillna("").to_dict().items()}


def _rerun_paper_detail(paper_id: str) -> None:
    preserve_reader_context_for_paper_id(paper_id, st.session_state)
    st.rerun()


def _refresh_reading_note_header_after_metadata_apply(paper_id: str) -> None:
    updated_record = _latest_record_for_paper(paper_id)
    if not updated_record:
        return

    draft_key = note_draft_key(updated_record)
    if draft_key in st.session_state:
        draft_result = refresh_reading_note_header(str(st.session_state.get(draft_key, "")), updated_record)
        if draft_result["changed"]:
            if has_unsaved_note_changes(updated_record, st.session_state):
                queue_note_header_refresh(
                    updated_record,
                    st.session_state,
                    str(draft_result["text"]),
                    notice="Header refresh available; unsaved changes kept.",
                    saved_to_file=False,
                )
                return
            refresh_note_header(updated_record)
            queue_note_header_refresh(
                updated_record,
                st.session_state,
                str(draft_result["text"]),
                notice="Header refreshed.",
                saved_to_file=True,
            )
        return

    file_result = refresh_note_header(updated_record)
    if file_result["changed"]:
        st.session_state[pending_note_reload_key(updated_record)] = True


def _scan_button(key: str) -> None:
    if st.button(
        "Scan papers (local sync)",
        key=key,
        help="Fast local file/index sync; metadata enrichment runs separately.",
    ):
        with st.status("Scanning local PDFs...", expanded=False) as status:
            update_index_from_scan()
            status.update(label="Paper index updated.", state="complete")
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
        st.dataframe(recent[["title", "filename", "status", "added_at"]], width="stretch", hide_index=True)


def library_page() -> None:
    st.title("Library")
    df = _index()

    archive_view = st.radio("Archive visibility", ("Active", "Include archived", "Archived only"), horizontal=True)
    df = filter_archived(df, include_archived=archive_view == "Include archived", archived_only=archive_view == "Archived only")
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
        width="stretch",
        hide_index=True,
    )

    if st.button("Open"):
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
    st.caption(
        " | ".join(
            [
                f"{record.get('filename', '')}",
                f"{record.get('journal', '') or 'journal unknown'}",
                f"{record.get('year', '') or 'year unknown'}",
                f"DOI: {record.get('doi', '') or 'not set'}",
            ]
        )
    )
    archived = str(record.get("is_archived", "false")).lower() == "true"
    if archived:
        st.info(f"Archived at {record.get('archived_at', '') or 'an unknown time'}. The PDF and linked data remain unchanged.")
    if st.button("Unarchive" if archived else "Archive", key=f"archive_{record['paper_id']}"):
        set_paper_archived(record["paper_id"], not archived)
        st.success("Paper unarchived." if archived else "Paper archived. No files were moved or deleted.")
        _rerun_paper_detail(record["paper_id"])

    render_reader_workspace(record)

    with st.expander("Project Links"):
        render_paper_project_links(record)

    title = record.get("title", "")
    abstract = record.get("abstract", "")
    keywords = record.get("keywords", "")
    journal = record.get("journal", "")
    tags = record.get("tags", "")

    with st.expander("Edit metadata"):
        with st.form(key=f"metadata_form_{record['paper_id']}"):
            title = st.text_input("Title", value=record.get("title", ""))
            authors = st.text_input("Authors", value=record.get("authors", ""))
            col1, col2 = st.columns(2)
            year = col1.text_input("Year", value=record.get("year", ""))
            journal = col2.text_input("Journal", value=record.get("journal", ""))
            doi = st.text_input("DOI", value=record.get("doi", ""))
            abstract = st.text_area("Abstract", value=record.get("abstract", ""), height=120)
            keywords = st.text_input("Keywords", value=record.get("keywords", ""))
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

            save_metadata = st.form_submit_button("Save")

        if save_metadata:
            update_paper_metadata(
                record["paper_id"],
                {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "journal": journal,
                    "doi": doi,
                    "abstract": abstract,
                    "keywords": keywords,
                    "tags": tags,
                    "status": status,
                    "reading_priority": reading_priority,
                },
            )
            _refresh_reading_note_header_after_metadata_apply(record["paper_id"])
            st.success("Metadata saved.")
            _rerun_paper_detail(record["paper_id"])

    form_values = {
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "journal": journal,
        "filename": record.get("filename", ""),
        "tags": tags,
    }
    with st.expander("Metadata assist"):
        metadata_assist_section(record, form_values)

    with st.expander("Debug paths"):
        st.write(f"Filename: `{record['filename']}`")
        st.write(f"Filepath: `{record['filepath']}`")
        st.write(f"Note path: `{record['note_path']}`")


def metadata_assist_section(record: dict[str, str], form_values: dict | None = None) -> None:
    st.subheader("Metadata Assist")
    current_doi = record.get("doi", "")
    st.write(f"Current DOI: `{current_doi or 'not set'}`")
    preview_key = f"crossref_preview_{record['paper_id']}"
    extraction_key = f"doi_extraction_{record['paper_id']}"
    enrichment_key = f"metadata_enrichment_{record['paper_id']}"
    doi_less_key = f"doi_less_metadata_candidate_{record['paper_id']}"
    metadata_profile = _metadata_assist_profile(record)

    if st.button("Enrich Metadata", type="primary"):
        normalized_current_doi = normalize_doi(current_doi)
        doi_result = enrich_paper_doi_from_pdf(record["paper_id"])
        detected_doi = str(doi_result.get("doi", ""))
        extraction_source = str(doi_result.get("source", "none"))
        saved = bool(doi_result.get("saved", False))
        message = str(doi_result.get("message", ""))
        if saved:
            _refresh_reading_note_header_after_metadata_apply(record["paper_id"])

        st.session_state[extraction_key] = {
            "doi": detected_doi,
            "source": extraction_source,
            "saved": saved,
            "message": message,
            "status": str(doi_result.get("status", "")),
        }

        doi_for_lookup = detected_doi or normalized_current_doi
        crossref_status = "not attempted"
        if doi_for_lookup:
            try:
                st.session_state[preview_key] = fill_metadata_gaps_from_pdf_profile(
                    record,
                    lookup_crossref_metadata(doi_for_lookup),
                    metadata_profile,
                )
                crossref_status = "metadata found; review the preview before accepting"
            except CrossrefLookupError as exc:
                crossref_status = f"failed: {exc}"
            except Exception:
                crossref_status = "failed: Crossref returned an unexpected response."
        elif not detected_doi:
            crossref_status = "not attempted; no DOI available"

        st.session_state[enrichment_key] = {
            "crossref_status": crossref_status,
        }
        if crossref_status.startswith("failed:") or crossref_status == "not attempted; no DOI available":
            st.session_state[doi_less_key] = build_doi_less_metadata_candidate(record)
        if saved or crossref_status.startswith("metadata found"):
            _rerun_paper_detail(record["paper_id"])

    extraction = st.session_state.get(extraction_key)
    enrichment = st.session_state.get(enrichment_key, {})
    crossref_status = enrichment.get("crossref_status", "")
    if crossref_status.startswith("failed:"):
        st.warning(f"Crossref lookup {crossref_status}")
    elif crossref_status.startswith("metadata found"):
        st.success("Crossref metadata found. Review the preview before accepting it.")
    if extraction:
        detected_doi = extraction.get("doi", "")
        if detected_doi:
            if extraction.get("saved"):
                st.success(extraction["message"])
            else:
                st.info(extraction["message"])
            doi_label = "Detected DOI" if extraction.get("status") == "doi_saved" else "DOI for lookup"
            st.write(f"{doi_label}: `{detected_doi}`")
            extraction_source = extraction.get("source", "none")
            if extraction.get("status") == "existing_doi":
                st.write("PDF DOI extraction: `not run; existing DOI used`")
            else:
                st.write(f"Extraction source: `{extraction_source}`")
            st.write(f"Saved to index: `{'yes' if extraction.get('saved') else 'no'}`")
            st.write(f"Crossref lookup status: `{enrichment.get('crossref_status', 'not attempted')}`")

            normalized_current_doi = normalize_doi(current_doi)
            if normalized_current_doi and detected_doi != normalized_current_doi:
                if st.button("Apply detected DOI"):
                    update_paper_metadata(
                        record["paper_id"],
                        {
                            "doi": detected_doi,
                            "doi_source": extraction.get("source", ""),
                            "extraction_source": extraction.get("source", ""),
                            "extraction_checked_at": _now_iso(),
                        },
                    )
                    _refresh_reading_note_header_after_metadata_apply(record["paper_id"])
                    st.session_state[extraction_key]["saved"] = True
                    st.session_state[extraction_key]["message"] = "Detected DOI was saved to this paper."
                    st.success("Saved detected DOI.")
                    _rerun_paper_detail(record["paper_id"])

            if st.button("Fetch Crossref metadata for detected DOI"):
                try:
                    st.session_state[preview_key] = fill_metadata_gaps_from_pdf_profile(
                        record,
                        lookup_crossref_metadata(detected_doi),
                        metadata_profile,
                    )
                    st.success("Crossref metadata found. Review the preview before accepting it.")
                    _rerun_paper_detail(record["paper_id"])
                except CrossrefLookupError as exc:
                    st.warning(str(exc))
                except Exception:
                    st.warning("Crossref returned an unexpected response.")
        else:
            st.info(extraction["message"])
            st.write("Detected DOI: `not found`")
            st.write(f"DOI extraction source: `{extraction.get('source', 'none')}`")
            st.write("Saved to index: `no`")
            st.write(f"Crossref lookup status: `{enrichment.get('crossref_status', 'not attempted')}`")

    if st.button("Find DOI-less metadata", key=f"doi_less_metadata_button_{record['paper_id']}"):
        st.session_state[doi_less_key] = build_doi_less_metadata_candidate(record)

    doi_less_candidate = st.session_state.get(doi_less_key)
    if doi_less_candidate:
        _render_doi_less_metadata_candidate(record, doi_less_candidate, doi_less_key)

    preview = st.session_state.get(preview_key)
    if preview:
        preview = fill_metadata_gaps_from_pdf_profile(record, preview, metadata_profile)
    profile = metadata_profile
    suggestion_record = build_tag_suggestion_record(
        record,
        form_values=form_values,
        crossref_preview=preview,
        paper_text_profile=profile,
    )
    suggestion_details = explain_tag_suggestions(suggestion_record)
    st.write("Suggested tags")
    with st.expander("Tag suggestion input"):
        st.write(f"PaperTextProfile: `{'available' if profile else 'not built'}`")
        st.write(f"Title: `{suggestion_record.get('title', '')}`")
        st.write(f"Abstract length: `{len(str(suggestion_record.get('abstract', '') or ''))}`")
        st.write(f"Keywords: `{suggestion_record.get('keywords', '')}`")
        note_sources = [
            field
            for field in ("note_summary", "note_methods", "note_evidence")
            if str(suggestion_record.get(field, "")).strip()
        ]
        st.write(f"Profile note sources: `{', '.join(note_sources) or 'none'}`")
        st.write(f"Journal: `{suggestion_record.get('journal', '')}`")
        st.write(f"Filename: `{suggestion_record.get('filename', '')}`")
        st.write(f"Crossref subjects: `{suggestion_record.get('crossref_subjects', '')}`")
        st.write(f"Existing tags: `{suggestion_record.get('tags', '')}`")
    if profile:
        _render_metadata_profile_preview(profile)
    if suggestion_details:
        st.caption("Candidate tags are added only to this paper unless promoted in Tag Manager.")
        selected_suggestion_ids = _render_grouped_tag_suggestions(
            suggestion_details,
            key_prefix=f"metadata_assist_{record['paper_id']}",
        )
        if st.button("Apply selected suggested tags", disabled=not selected_suggestion_ids):
            selected_tags = selected_suggestion_tag_values(suggestion_details, selected_suggestion_ids)
            merged_tags = merge_tags(record.get("tags", ""), selected_tags)
            update_paper_metadata(record["paper_id"], {"tags": merged_tags})
            _refresh_reading_note_header_after_metadata_apply(record["paper_id"])
            st.success("Selected suggested tags added.")
            _rerun_paper_detail(record["paper_id"])
    else:
        st.caption("No new tag suggestions.")

    with st.expander("Advanced manual lookup"):
        if st.button("Lookup Crossref by DOI"):
            _lookup_crossref_by_current_doi(current_doi, preview_key, record, metadata_profile)

    if not preview:
        return

    st.write("Crossref preview")
    st.write("Metadata source: Crossref")
    if preview.get("metadata_warning"):
        st.warning(preview["metadata_warning"])
    field_sources = preview.get("field_sources", {}) if isinstance(preview.get("field_sources"), dict) else {}
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "field": field,
                    "value": preview.get(field, ""),
                    "source": field_sources.get(field, "crossref" if preview.get(field, "") else ""),
                }
                for field in (
                    "title",
                    "authors",
                    "year",
                    "journal",
                    "abstract",
                    "keywords",
                    "crossref_subjects",
                    "doi",
                    "metadata_source",
                    "metadata_confidence",
                )
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    if st.button("Apply Crossref metadata"):
        accept_crossref_metadata(record["paper_id"], preview)
        _refresh_reading_note_header_after_metadata_apply(record["paper_id"])
        st.session_state.pop(preview_key, None)
        st.success("Crossref metadata accepted.")
        _rerun_paper_detail(record["paper_id"])


def _render_grouped_tag_suggestions(suggestion_details: list[dict], *, key_prefix: str) -> list[str]:
    selected_ids: list[str] = []
    known = [item for item in suggestion_details if str(item.get("kind", "known_canonical")) == "known_canonical"]
    rejected = [
        item
        for item in suggestion_details
        if str(item.get("kind", "")) == "rejected_candidate" or str(item.get("quality", "")) == "rejected"
    ]
    candidates = [item for item in suggestion_details if item not in known and item not in rejected]

    if known:
        st.caption("Known canonical suggestions")
        selected_ids.extend(_render_suggestion_items(known, key_prefix=key_prefix))
    if candidates:
        st.caption("Candidate phrase suggestions")
        selected_ids.extend(_render_suggestion_items(candidates, key_prefix=f"{key_prefix}_candidate"))
    if rejected:
        with st.expander("Rejected candidate phrases"):
            _render_suggestion_items(rejected, key_prefix=f"{key_prefix}_rejected", force_disabled=True)
    return selected_ids


def _render_suggestion_items(
    suggestion_details: list[dict],
    *,
    key_prefix: str,
    force_disabled: bool = False,
) -> list[str]:
    selected_ids: list[str] = []
    for category, items in group_suggestions_by_category(suggestion_details).items():
        st.write(f"**{category}**")
        for detail in items:
            label = detail.get("display") or detail.get("canonical") or detail.get("tag")
            kind = str(detail.get("kind", "known_canonical")).replace("_", " ")
            quality = str(detail.get("quality", ""))
            quality_label = f", {quality}" if quality and kind != "known canonical" else ""
            source = str(detail.get("source", ""))
            source_label = str(detail.get("source_label", "") or source)
            matched_text = str(detail.get("matched_text", ""))
            reason = str(detail.get("reason", ""))
            quality_reason = str(detail.get("quality_reason") or detail.get("rejection_reason") or "")
            source_label = f" from {source_label}" if source_label else ""
            match_label = f" matched `{matched_text}`" if matched_text else ""
            selection_id = suggestion_selection_id(detail)
            selectable = bool(detail.get("selectable", not force_disabled)) and not force_disabled
            selected = st.checkbox(
                f"{label} ({kind}{quality_label})",
                key=f"{key_prefix}_{selection_id}",
                disabled=not selectable,
            )
            if selected and selectable:
                selected_ids.append(selection_id)
            st.caption(f"{source_label}{match_label}".strip() or "No match details.")
            if quality and kind != "known canonical":
                quality_caption = f"Quality: `{quality}`"
                if quality_reason:
                    quality_caption += f" - {quality_reason}"
                st.caption(quality_caption)
            if reason:
                st.caption(reason)
            snippet = _tag_suggestion_snippet(detail)
            if snippet:
                st.caption(f"Evidence: {snippet}")
    return selected_ids


def _tag_suggestion_snippet(suggestion: dict) -> str:
    evidence = suggestion.get("evidence", [])
    if not isinstance(evidence, list):
        return ""
    for item in evidence:
        if isinstance(item, dict) and str(item.get("snippet", "")).strip():
            return str(item["snippet"]).strip()
    return ""


def _render_doi_less_metadata_candidate(
    record: dict[str, str],
    candidate: dict[str, object],
    candidate_key: str,
) -> None:
    st.write("DOI-less metadata candidate")
    st.caption(
        f"Source: `{candidate.get('source', 'none')}` | "
        f"Confidence: `{candidate.get('confidence', 'none')}` | "
        f"arXiv ID: `{candidate.get('arxiv_id', '') or 'not found'}`"
    )
    diagnostics = candidate.get("diagnostics", [])
    if diagnostics:
        with st.expander("DOI-less metadata diagnostics"):
            for diagnostic in diagnostics:
                st.write(f"- {diagnostic}")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "field": field,
                    "candidate": candidate.get(field, ""),
                    "current": record.get(field, ""),
                }
                for field in ("title", "authors", "year", "abstract", "doi")
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    overwrite = st.checkbox(
        "Replace existing non-empty metadata fields",
        key=f"doi_less_overwrite_{record['paper_id']}",
    )
    plan = build_metadata_candidate_update(record, candidate, overwrite=overwrite)
    if plan["updates"]:
        with st.expander("Fields that will be applied"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"field": field, "value": value}
                        for field, value in plan["updates"].items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info("This candidate has no new metadata fields to apply with the current overwrite setting.")

    skipped = plan["skipped_existing_fields"]
    if skipped:
        st.caption("Existing non-empty fields will be preserved unless replacement is checked.")
        st.write(", ".join(f"`{field}`" for field in skipped))

    col1, col2 = st.columns(2)
    if col1.button(
        "Apply DOI-less metadata",
        key=f"doi_less_apply_{record['paper_id']}",
        disabled=not bool(plan["updates"]),
    ):
        result = apply_metadata_candidate_to_index(record["paper_id"], candidate, overwrite=overwrite)
        _refresh_reading_note_header_after_metadata_apply(record["paper_id"])
        st.session_state.pop(candidate_key, None)
        updated = ", ".join(result["updated_fields"]) if result["updated_fields"] else "none"
        st.success(f"DOI-less metadata applied. Updated fields: {updated}.")
        _rerun_paper_detail(record["paper_id"])
    if col2.button("Clear DOI-less candidate", key=f"doi_less_clear_{record['paper_id']}"):
        st.session_state.pop(candidate_key, None)
        _rerun_paper_detail(record["paper_id"])


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _metadata_assist_profile(record: dict[str, str]):
    profile = load_profile(str(record.get("paper_id", "")))
    if profile is not None:
        return profile
    try:
        return build_paper_text_profile(record)
    except (OSError, ValueError):
        return None


def _render_metadata_profile_preview(profile) -> None:
    with st.expander("PaperTextProfile preview"):
        st.write(f"Title: `{profile.title}`")
        st.write(f"Abstract characters: `{len(profile.abstract)}`")
        st.write(f"Keywords: `{', '.join(profile.keywords) or 'none'}`")
        st.write(f"Article type: `{profile.article_type}`")
        headings = ", ".join(profile.section_headings) or "none"
        st.write(f"Section headings: `{headings}`")
        if profile.extraction_warnings:
            st.write("Extraction warnings")
            for warning in profile.extraction_warnings:
                st.write(f"- {warning}")


def _lookup_crossref_by_current_doi(current_doi: str, preview_key: str, record: dict[str, str], profile) -> None:
    normalized = normalize_doi(current_doi)
    if not normalized:
        st.warning("Enter and save a DOI before looking up Crossref metadata.")
    elif not is_probable_doi(normalized):
        st.warning("The DOI does not look valid.")
    else:
        try:
            st.session_state[preview_key] = fill_metadata_gaps_from_pdf_profile(
                record,
                lookup_crossref_metadata(normalized),
                profile,
            )
            st.success("Crossref metadata found. Review the preview before accepting it.")
            _rerun_paper_detail(record["paper_id"])
        except CrossrefLookupError as exc:
            st.warning(str(exc))
        except Exception:
            st.warning("Crossref returned an unexpected response.")


def settings_page() -> None:
    st.title("Settings")
    st.caption("System status, library maintenance, external-service diagnostics, and local backups.")
    render_system_settings()
    st.divider()
    render_library_maintenance_settings()
    st.divider()
    render_external_services_settings()
    st.divider()
    render_backup_settings()


def render_system_settings() -> None:
    st.header("System")
    st.caption("Runtime details and resolved local workspace paths.")
    col1, col2, col3 = st.columns(3)
    col1.metric("App version", APP_VERSION)
    col2.metric("Python", platform.python_version())
    col3.metric("Streamlit", st.__version__)

    with st.expander("Workspace paths", expanded=True):
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

    backends = get_text_extraction_backends()
    with st.expander("Runtime and storage details"):
        st.write(
            "PDF text extraction: "
            + ", ".join(
                f"{name}={'available' if available else 'unavailable'}"
                for name, available in backends.items()
            )
        )
        st.write(f"Pandas: `{pd.__version__}`")
        st.write("Paper index columns")
        st.code("\n".join(INDEX_COLUMNS))


def render_library_maintenance_settings() -> None:
    st.header("Library Maintenance")
    st.caption("Read-only health diagnostics first, followed by explicit maintenance actions.")
    _render_library_health_check()
    _render_tag_rules_settings()
    st.subheader("Maintenance Actions")
    st.caption("These workflows require preview or confirmation before changing library files.")
    _render_pdf_inbox()
    _render_paper_file_hygiene()


def _render_tag_rules_settings() -> None:
    st.subheader("Tag Book")
    tag_book = load_tag_book()
    rules = load_tag_rules()
    canonical_registry = load_canonical_tags()
    validation_warnings = validate_tag_book(tag_book)
    compatibility_warnings = validate_tag_rules(rules)
    tag_audit = audit_canonical_tags(_index().to_dict("records"), canonical_registry)
    near_duplicates = preview_near_duplicate_tags(tag_book)
    st.write(f"Tag Book path: `{DEFAULT_TAG_BOOK_DIR}`")
    st.write(f"Rulebook path: `{DEFAULT_RULE_PATH}`")
    st.write(f"Suggestion rules: `{len(rules)}`")
    st.write(f"Canonical registry: `{DEFAULT_CANONICAL_TAG_PATH}`")
    st.write(f"Canonical tags: `{len(canonical_registry)}`")
    if validation_warnings:
        st.warning("Tag Book validation warnings:")
        for warning in validation_warnings:
            st.write(f"- {warning}")
    else:
        st.success("Tag Book validation passed.")
    if compatibility_warnings:
        with st.expander("Compatibility rule warnings"):
            for warning in compatibility_warnings:
                st.write(f"- {warning}")
    st.write(f"Unknown library tags: `{len(tag_audit['unknown_tags'])}`")
    st.write(f"Unused canonical tags: `{len(tag_audit['unused_canonical_tags'])}`")
    st.write(f"Near-duplicate preview: `{len(near_duplicates)}`")
    st.write("Canonical alias collisions")
    if tag_audit["alias_collisions"]:
        for alias, owners in tag_audit["alias_collisions"].items():
            st.warning(f"`{alias}` maps to multiple tags: {', '.join(owners)}")
    else:
        st.write("None")
    st.caption("Use Tag Manager to review, merge, or register library tags.")


def render_external_services_settings() -> None:
    st.header("External Services")
    st.caption("Optional network diagnostics. Local library workflows remain available while offline.")
    st.subheader("Crossref Diagnostics")
    dependency_versions = crossref_dependency_versions()
    st.caption(
        "Crossref dependencies: "
        + ", ".join(f"{name} {version}" for name, version in dependency_versions.items())
    )
    proxy_vars = proxy_environment()
    if proxy_vars:
        st.warning(
            "Proxy environment variables are set: "
            + ", ".join(f"{name}={value}" for name, value in proxy_vars.items())
        )
    if st.button("Test Crossref connection", key="test_crossref_connection"):
        result = check_crossref_connectivity()
        if result["ok"]:
            st.success(f"{result['message']} HTTP status: {result['status_code']}")
        else:
            st.warning(result["message"])
    st.write(
        "Crossref requires internet access but no API key. Metadata is previewed before acceptance and remains "
        "stored locally in data/paper_index.csv. Fill incomplete fields manually before using Paper Hygiene."
    )


def render_backup_settings() -> None:
    st.header("Backup")
    st.caption("Create additive local snapshots. Restore remains a documented manual workflow.")
    st.subheader("Backup Snapshot")
    st.write(
        "Create a timestamped ZIP under exports/. Light snapshots contain library metadata and notes; "
        "full snapshots also contain every managed PDF under papers/."
    )
    st.caption(
        "Source code belongs in GitHub. Backup snapshots are for private local library data. "
        "Extracted-text and paper-profile caches are intentionally excluded because they are regenerable."
    )
    snapshot_mode = st.radio(
        "Snapshot type",
        options=("Light - metadata and notes", "Full - metadata, notes, and PDFs"),
        horizontal=True,
        key="backup_snapshot_type",
    )
    include_pdfs = snapshot_mode.startswith("Full")
    full_confirmation = True
    if include_pdfs:
        st.warning("Full snapshots can be large because they include the entire papers/ directory.")
        full_confirmation = st.checkbox(
            "I understand this full snapshot includes all managed PDFs.",
            key="backup_snapshot_full_confirm",
        )
    if st.button(
        "Create backup snapshot",
        key="create_backup_snapshot",
        disabled=include_pdfs and not full_confirmation,
    ):
        try:
            with st.status("Creating backup snapshot...", expanded=False) as status:
                st.session_state["backup_snapshot_result"] = create_backup_snapshot(include_pdfs=include_pdfs)
                status.update(label="Backup snapshot created.", state="complete")
        except Exception as exc:
            st.error("The backup snapshot could not be created. Check file access and available disk space.")
            with st.expander("Backup error details"):
                st.write(f"Exception: `{exc.__class__.__name__}`")
                st.write(str(exc))

    snapshot_result = st.session_state.get("backup_snapshot_result")
    if snapshot_result:
        manifest = snapshot_result["manifest"]
        st.success(f"Snapshot created: {snapshot_result['snapshot_path']}")
        st.caption(
            f"{manifest['snapshot_type'].title()} snapshot | "
            f"{manifest['counts']['included_files']} files | {manifest['counts']['pdfs']} PDFs"
        )
        with st.expander("Snapshot policy"):
            policy = manifest.get("policy", {})
            st.write(policy.get("purpose", ""))
            st.write("Excluded by default:")
            st.code("\n".join(policy.get("excluded_by_default", [])))
    st.caption(f"Restore is manual in v{APP_VERSION}; creating a snapshot never changes library data.")


def _render_library_health_check() -> None:
    st.subheader("Library Health Check")
    st.write(
        "Run read-only checks for missing or unindexed PDFs, duplicate identities, incomplete metadata, "
        "orphaned records, corrupt JSON stores, backup coverage, and stale extracted text."
    )
    if st.button("Run library health check", key="run_library_health_check"):
        try:
            with st.status("Checking library health...", expanded=False) as status:
                st.session_state["library_health_report"] = run_library_health_check()
                status.update(label="Library health check complete.", state="complete")
            st.success("Library health check complete.")
        except JsonStoreError as exc:
            st.error("A local JSON file could not be read. No library data was changed.")
            st.warning(exc.suggested_action)
            with st.expander("JSON error details"):
                st.write(f"Path: `{exc.path}`")
                st.write(f"Issue: {exc.summary}")
                st.write(f"Exception: `{exc.__class__.__name__}`")
        except Exception as exc:
            st.error("The library health check could not finish. Check access to local library files.")
            with st.expander("Health check error details"):
                st.write(f"Exception: `{exc.__class__.__name__}`")
                st.write(str(exc))

    success_message = st.session_state.pop("library_health_repair_success", "")
    if success_message:
        st.success(success_message)

    report = st.session_state.get("library_health_report")
    if not report:
        return
    summary = report["summary"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Index rows", summary["index_rows"])
    col2.metric("Managed PDFs", summary["managed_pdfs"])
    col3.metric("Issues", summary["issue_count"])
    if report["healthy"]:
        st.success("No library health issues were detected.")
        return
    st.warning("Library health issues were detected. Review the sections below before moving or restoring data.")
    sections = (
        ("Missing indexed PDFs", "missing_pdfs"),
        ("Unindexed PDFs", "unindexed_pdfs"),
        ("Duplicate filenames", "duplicate_filenames"),
        ("Duplicate PDF hashes", "duplicate_pdf_hashes"),
        ("Ignored exact duplicates", "ignored_duplicates"),
        ("Quarantined caches", "quarantined_caches"),
        ("Duplicate DOI values", "duplicate_dois"),
        ("Missing metadata", "missing_metadata"),
        ("Orphan notes", "orphan_notes"),
        ("Orphan note blocks", "orphan_note_blocks"),
        ("Orphan project links", "orphan_project_links"),
        ("Orphan extracted text caches", "orphan_extracted_text"),
        ("Stale extracted text", "stale_extracted_text"),
        ("Noncanonical PDF paths", "noncanonical_filepaths"),
        ("Corrupt or invalid JSON stores", "corrupt_json"),
        ("Backup snapshot concerns", "backup_snapshot_warnings"),
        ("Diagnostic errors", "errors"),
    )
    for title, key in sections:
        items = report[key]
        if not items:
            continue
        with st.expander(f"{title} ({len(items)})"):
            _render_health_issue_guidance(report, key)
            if key == "missing_pdfs":
                _render_missing_pdf_repair(items)
            elif key == "duplicate_pdf_hashes":
                _render_duplicate_pdf_hash_review(items)
            elif key == "ignored_duplicates":
                _render_ignored_duplicate_review(items)
            elif key == "quarantined_caches":
                _render_quarantined_cache_review(items)
            elif key == "corrupt_json":
                _render_corrupt_storage_review(items)
            elif key == "orphan_notes":
                _render_orphan_note_review(items)
            elif key == "orphan_note_blocks":
                _render_orphan_note_block_review(items)
            elif key == "orphan_project_links":
                _render_orphan_project_link_repair(items)
            elif isinstance(items[0], dict):
                st.dataframe(pd.DataFrame(items), width="stretch", hide_index=True)
            else:
                st.dataframe(pd.DataFrame({"path_or_message": items}), width="stretch", hide_index=True)


def _render_health_issue_guidance(report: dict[str, object], key: str) -> None:
    guidance = dict(report.get("issue_guidance", {}).get(key, {})) if isinstance(report.get("issue_guidance"), dict) else {}
    if not guidance:
        return
    severity = str(guidance.get("severity", "review")).title()
    category = str(guidance.get("category", "health"))
    st.write(f"**{severity} - {category}**")
    st.write(str(guidance.get("meaning", "")))
    st.info(str(guidance.get("next_action", "")))


def _refresh_health_after_action(message: str) -> None:
    st.session_state["library_health_report"] = run_library_health_check()
    st.session_state["library_health_repair_success"] = message


def _render_corrupt_storage_review(items: list[dict[str, object]]) -> None:
    groups: dict[str, list[dict[str, object]]] = {}
    for item in items:
        groups.setdefault(str(item.get("storage_class", "unclassified")), []).append(item)
    for storage_class, records in groups.items():
        st.write(f"**{storage_class.title()}**")
        for index, item in enumerate(records):
            path = str(item.get("path", ""))
            st.error(str(item.get("issue", "Storage corruption detected.")))
            st.write(f"Safe default: {item.get('suggested_action', 'Export a recovery copy before repair.')}")
            with st.expander("Technical details"):
                st.json(item)
            col1, col2 = st.columns(2)
            if col1.button("Export recovery copy", key=f"recovery_export_{index}_{path}"):
                try:
                    result = export_recovery_copy(path, workspace_root=PROJECT_ROOT, recovery_dir=RECOVERY_DIR, storage_class=storage_class, reason=str(item.get("issue", "Health Check diagnosis")))
                except (OSError, StorageRecoveryError) as exc:
                    st.error(f"Recovery-copy export failed for this target: {exc}")
                else:
                    _refresh_health_after_action(f"Recovery copy exported to {result['copy_path']}. The source was unchanged.")
                    st.rerun()
            if bool(item.get("rebuildable", False)):
                confirmed = col2.checkbox("Confirm quarantine", key=f"quarantine_confirm_{index}_{path}")
                if col2.button("Quarantine cache", key=f"quarantine_{index}_{path}", disabled=not confirmed):
                    try:
                        result = quarantine_file(path, workspace_root=PROJECT_ROOT, quarantine_dir=QUARANTINE_DIR, storage_class=storage_class, reason=str(item.get("issue", "Health Check diagnosis")), rebuildable=True, confirm=True)
                    except (OSError, StorageRecoveryError) as exc:
                        st.error(f"Quarantine failed; the active target was preserved: {exc}")
                    else:
                        _refresh_health_after_action(f"Cache quarantined after verified recovery copy: {result.get('copy_path', path)}. Rebuild remains explicit.")
                        st.rerun()
            else:
                col2.caption("Manual repair only. Critical user state cannot be quarantined by default.")
    manifests = sorted(QUARANTINE_DIR.glob("*.manifest.json")) if QUARANTINE_DIR.is_dir() else []
    if manifests:
        st.write("**Restore quarantined cache**")
        selected = st.selectbox("Quarantine manifest", manifests, format_func=lambda path: path.name)
        confirmed = st.checkbox("Confirm restore; an existing active destination will never be overwritten.", key="restore_quarantine_confirm")
        if st.button("Restore", disabled=not confirmed):
            try:
                result = restore_quarantined_file(selected, workspace_root=PROJECT_ROOT, confirm=True)
            except (OSError, StorageRecoveryError) as exc:
                st.error(f"Restore failed for this target: {exc}")
            else:
                _refresh_health_after_action(f"Quarantined bytes restored to {result['destination_path']}; the quarantine copy was retained.")
                st.rerun()


def _render_ignored_duplicate_review(items: list[dict[str, object]]) -> None:
    st.info("These exact path/content decisions are informational. A path or content change makes the decision inapplicable.")
    for index, item in enumerate(items):
        st.write(f"`{item.get('workspace_relative_path', item.get('filepath', ''))}`")
        st.code(f"SHA-256: {item.get('pdf_sha256', '')}")
        if st.button("Unignore", key=f"unignore_duplicate_{index}_{item.get('pdf_sha256', '')}"):
            try:
                changed = unignore_exact_duplicate(str(item.get("filepath", "")), decision_path=LIFECYCLE_DECISIONS_JSON, workspace_root=PROJECT_ROOT)
            except (JsonStoreError, ValueError) as exc:
                st.error(f"Unignore failed: {exc}")
            else:
                _refresh_health_after_action("Exact duplicate decision removed." if changed else "The decision was already absent.")
                st.rerun()


def _render_quarantined_cache_review(items: list[dict[str, object]]) -> None:
    st.info("Restore is explicit, verifies retained bytes, refuses to overwrite an active file, and retains the quarantine copy.")
    for index, item in enumerate(items):
        st.write(f"Original: `{item.get('original_path', '')}`")
        with st.expander("Technical details"):
            st.json(item)
        confirmed = st.checkbox("Confirm restore", key=f"restore_quarantine_confirm_{index}")
        if st.button("Restore quarantined cache", key=f"restore_quarantine_{index}", disabled=not confirmed):
            try:
                result = restore_quarantined_file(str(item.get("manifest_path", "")), workspace_root=PROJECT_ROOT, confirm=True)
            except (OSError, StorageRecoveryError) as exc:
                st.error(f"Restore failed for this target: {exc}")
            else:
                _refresh_health_after_action(f"Quarantined bytes restored to {result['destination_path']}; the quarantine copy was retained.")
                st.rerun()


def _duplicate_pdf_hash_rows(group: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record in group.get("indexed_records", []):
        if not isinstance(record, dict):
            continue
        rows.append(
            {
                "index_state": "indexed",
                "paper_id": record.get("paper_id", ""),
                "title": record.get("title", ""),
                "filename": record.get("filename", ""),
                "filepath": record.get("filepath", ""),
                "status": record.get("status", ""),
                "note_file_count": record.get("note_file_count", 0),
                "note_block_count": record.get("note_block_count", 0),
                "project_link_count": record.get("project_link_count", 0),
                "review_action": "Choose keep, reconnect, ignore, or confirmed index-row removal below.",
            }
        )
    for duplicate_file in group.get("unindexed_files", []):
        if not isinstance(duplicate_file, dict):
            continue
        rows.append(
            {
                "index_state": "unindexed",
                "paper_id": "",
                "title": "",
                "filename": duplicate_file.get("filename", ""),
                "filepath": duplicate_file.get("filepath", ""),
                "status": "",
                "note_file_count": 0,
                "note_block_count": 0,
                "project_link_count": 0,
                "review_action": duplicate_file.get("review_action", "Do not add to index yet; handle later."),
            }
        )
    return rows


def _render_duplicate_pdf_hash_review(items: list[dict[str, object]]) -> None:
    st.caption(
        "No same-hash duplicates are merged automatically. Repair actions preserve PDFs, notes, note blocks, "
        "project links, and extracted text unless a confirmed index-row removal is selected."
    )
    summary_rows = [
        {
            "classification": item.get("classification", ""),
            "pdf_sha256": item.get("pdf_sha256", ""),
            "indexed_record_count": item.get("indexed_record_count", 0),
            "unindexed_file_count": item.get("unindexed_file_count", 0),
        }
        for item in items
    ]
    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)
    for index, group in enumerate(items, start=1):
        classification = str(group.get("classification", "duplicate"))
        pdf_sha256 = str(group.get("pdf_sha256", ""))
        st.write(f"Group {index}: `{classification}`")
        st.code(f"pdf_sha256: {pdf_sha256 or 'unavailable'}")
        rows = _duplicate_pdf_hash_rows(group)
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        for file_index, duplicate_file in enumerate(group.get("unindexed_files", [])):
            if not isinstance(duplicate_file, dict) or not duplicate_file.get("filepath"):
                continue
            filepath = str(duplicate_file["filepath"])
            col1, col2 = st.columns(2)
            if col1.button("Keep for review", key=f"keep_unindexed_{index}_{file_index}_{pdf_sha256}"):
                st.info("No changes were made. The duplicate remains visible.")
            if col2.button("Ignore this exact duplicate", key=f"ignore_unindexed_{index}_{file_index}_{pdf_sha256}"):
                try:
                    path = Path(filepath)
                    stat = path.stat()
                    ignore_exact_duplicate(filepath, pdf_sha256, size_bytes=stat.st_size, modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), decision_path=LIFECYCLE_DECISIONS_JSON, workspace_root=PROJECT_ROOT)
                except (OSError, JsonStoreError, ValueError) as exc:
                    st.error(f"Ignore decision could not be saved: {exc}")
                else:
                    _refresh_health_after_action("Exact duplicate ignored. No PDF, index row, paper_id, note, or project link was changed.")
                    st.rerun()
        indexed_records = [
            record for record in group.get("indexed_records", []) if isinstance(record, dict) and record.get("paper_id")
        ]
        if not indexed_records:
            st.info("Only unindexed PDFs are in this group. Keep or ignore them for now; no index row can be repaired.")
            continue
        labels = {
            str(record.get("paper_id", "")): (
                f"{record.get('title', '') or record.get('filename', '') or record.get('paper_id', '')} "
                f"({record.get('paper_id', '')})"
            )
            for record in indexed_records
        }
        selected_paper_id = st.selectbox(
            "Indexed duplicate row",
            options=list(labels),
            format_func=lambda paper_id: labels.get(paper_id, paper_id),
            key=f"duplicate_pdf_row_{index}_{pdf_sha256}",
        )
        action = st.radio(
            "Duplicate action",
            options=("Keep", "Reconnect", "Remove index row"),
            horizontal=True,
            key=f"duplicate_pdf_action_{index}_{pdf_sha256}_{selected_paper_id}",
        )
        if action == "Keep":
            if st.button("Keep duplicate rows", key=f"duplicate_pdf_keep_{index}_{selected_paper_id}"):
                st.info("No changes were made. This duplicate group remains visible in health checks.")
        elif action == "Reconnect":
            candidate_files = [
                candidate
                for candidate in group.get("unindexed_files", [])
                if isinstance(candidate, dict) and candidate.get("filepath")
            ]
            if not candidate_files:
                st.info("No unindexed same-hash PDF is available for reconnect in this group.")
                continue
            target_labels = {
                str(candidate.get("filepath", "")): str(candidate.get("filename", "") or candidate.get("filepath", ""))
                for candidate in candidate_files
            }
            selected_target = st.selectbox(
                "Reconnect target PDF",
                options=list(target_labels),
                format_func=lambda path: target_labels.get(path, path),
                key=f"duplicate_pdf_reconnect_target_{index}_{selected_paper_id}",
            )
            plan = build_duplicate_reconnect_plan(selected_paper_id, selected_target)
            st.write(f"Reconnect status: `{plan['status']}`")
            st.write(plan["message"])
            st.code(
                "\n".join(
                    [
                        f"paper_id: {plan.get('paper_id', '')}",
                        f"current filepath: {plan.get('current_filepath', '')}",
                        f"target filepath:  {plan.get('target_path', '')}",
                        f"stored SHA-256:  {plan.get('current_pdf_sha256', '') or 'unavailable'}",
                        f"target SHA-256:  {plan.get('target_pdf_sha256', '') or 'unavailable'}",
                        f"updates: {plan.get('updates', '')}",
                        f"preserves: {plan.get('preserves', '')}",
                    ]
                )
            )
            mismatch_confirmed = True
            if plan["requires_hash_mismatch_confirmation"]:
                st.warning("The selected PDF has a different SHA-256 from this index row.")
                mismatch_confirmed = st.checkbox(
                    "I understand this reconnect uses a different SHA-256.",
                    key=f"duplicate_pdf_reconnect_mismatch_{index}_{selected_paper_id}",
                )
            reconnect_confirmed = st.checkbox(
                "I understand reconnect updates only file identity fields and keeps paper_id-linked data.",
                key=f"duplicate_pdf_reconnect_confirm_{index}_{selected_paper_id}",
                disabled=not bool(plan["can_reconnect"]),
            )
            if st.button(
                "Reconnect duplicate row",
                key=f"duplicate_pdf_reconnect_apply_{index}_{selected_paper_id}",
                disabled=not reconnect_confirmed or not mismatch_confirmed or not bool(plan["can_reconnect"]),
            ):
                try:
                    result = reconnect_duplicate_pdf(
                        selected_paper_id,
                        selected_target,
                        confirm_hash_mismatch=bool(mismatch_confirmed),
                    )
                except FileLifecycleRepairError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop("library_health_report", None)
                    st.session_state["library_health_repair_success"] = result["message"]
                    st.rerun()
        else:
            plan = build_duplicate_remove_plan(selected_paper_id)
            st.warning(plan["warning"])
            st.write(f"Remove status: `{plan['status']}`")
            st.write(plan["message"])
            st.code(
                "\n".join(
                    [
                        f"paper_id: {plan.get('paper_id', '')}",
                        f"filepath: {plan.get('filepath', '')}",
                        f"pdf_sha256: {plan.get('pdf_sha256', '') or 'unavailable'}",
                        f"same-hash indexed rows: {plan.get('same_hash_index_row_count', 0)}",
                        f"removes: {plan.get('removes', '')}",
                        f"preserves: {plan.get('preserves', '')}",
                    ]
                )
            )
            remove_confirmed = st.checkbox(
                "I understand this removes only the selected paper_index.csv row.",
                key=f"duplicate_pdf_remove_confirm_{index}_{selected_paper_id}",
                disabled=not bool(plan["can_remove"]),
            )
            if st.button(
                "Remove duplicate index row",
                key=f"duplicate_pdf_remove_apply_{index}_{selected_paper_id}",
                disabled=not remove_confirmed or not bool(plan["can_remove"]),
            ):
                try:
                    result = remove_duplicate_index_row(selected_paper_id, confirm=True)
                except FileLifecycleRepairError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop("library_health_report", None)
                    st.session_state["library_health_repair_success"] = result["message"]
                    st.rerun()


def _indexed_paper_labels() -> dict[str, str]:
    dataframe = _index()
    labels: dict[str, str] = {}
    if dataframe.empty or "paper_id" not in dataframe.columns:
        return labels
    for record in dataframe.to_dict("records"):
        paper_id = str(record.get("paper_id", "")).strip()
        if not paper_id:
            continue
        labels[paper_id] = f"{record.get('title', '') or record.get('filename', '') or paper_id} ({paper_id})"
    return labels


def _render_orphan_note_review(items: list[dict[str, object]]) -> None:
    st.caption(ORPHAN_PRESERVE_ACTION)
    st.dataframe(pd.DataFrame(items), width="stretch", hide_index=True)
    paper_ids = [str(item.get("paper_id", "")) for item in items if item.get("paper_id")]
    if not paper_ids:
        return
    selected_orphan_id = st.selectbox(
        "Orphan note",
        options=paper_ids,
        key="orphan_note_selected_id",
    )
    target_labels = _indexed_paper_labels()
    if st.button("Export orphan note", key=f"orphan_note_export_{selected_orphan_id}"):
        try:
            result = export_orphan_note(selected_orphan_id)
        except OrphanRepairError as exc:
            st.error(str(exc))
        else:
            st.success(result["message"])
            st.caption(result["export_path"])
    if target_labels:
        selected_target_id = st.selectbox(
            "Reattach note to paper",
            options=list(target_labels),
            format_func=lambda paper_id: target_labels.get(paper_id, paper_id),
            key=f"orphan_note_target_{selected_orphan_id}",
        )
        plan = build_orphan_note_repair_plan(selected_orphan_id, selected_target_id)
        st.write(f"Reattach status: `{plan['status']}`")
        st.write(plan["message"])
        reattach_confirmed = st.checkbox(
            "I understand this moves orphan note content into the selected paper note.",
            key=f"orphan_note_reattach_confirm_{selected_orphan_id}",
            disabled=not bool(plan["can_reattach"]),
        )
        if st.button(
            "Reattach orphan note",
            key=f"orphan_note_reattach_apply_{selected_orphan_id}",
            disabled=not reattach_confirmed or not bool(plan["can_reattach"]),
        ):
            try:
                result = reattach_orphan_note(selected_orphan_id, selected_target_id, confirm=True)
            except OrphanRepairError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("library_health_report", None)
                st.session_state["library_health_repair_success"] = result["message"]
                st.rerun()
    with st.expander("Delete orphan note"):
        st.warning("Delete is permanent. Export first if the content may be needed later.")
        delete_confirmed = st.checkbox(
            "I understand this deletes only the orphan note file.",
            key=f"orphan_note_delete_confirm_{selected_orphan_id}",
        )
        if st.button(
            "Delete orphan note",
            key=f"orphan_note_delete_apply_{selected_orphan_id}",
            disabled=not delete_confirmed,
        ):
            try:
                result = delete_orphan_note(selected_orphan_id, confirm=True)
            except OrphanRepairError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("library_health_report", None)
                st.session_state["library_health_repair_success"] = result["message"]
                st.rerun()


def _render_orphan_note_block_review(items: list[dict[str, object]]) -> None:
    st.caption(ORPHAN_PRESERVE_ACTION)
    summary_rows = [{key: value for key, value in item.items() if key != "blocks"} for item in items]
    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)
    for item in items:
        blocks = item.get("blocks", [])
        if not blocks:
            continue
        st.write(f"Blocks for `{item.get('paper_id', '')}`")
        st.dataframe(pd.DataFrame(blocks), width="stretch", hide_index=True)
    paper_ids = [str(item.get("paper_id", "")) for item in items if item.get("paper_id")]
    if not paper_ids:
        return
    selected_orphan_id = st.selectbox(
        "Orphan note-block file",
        options=paper_ids,
        key="orphan_note_block_selected_id",
    )
    if st.button("Export orphan note blocks", key=f"orphan_note_block_export_{selected_orphan_id}"):
        try:
            result = export_orphan_note_blocks(selected_orphan_id)
        except OrphanRepairError as exc:
            st.error(str(exc))
        else:
            st.success(result["message"])
            st.caption(result["export_path"])
    target_labels = _indexed_paper_labels()
    if target_labels:
        selected_target_id = st.selectbox(
            "Reattach blocks to paper",
            options=list(target_labels),
            format_func=lambda paper_id: target_labels.get(paper_id, paper_id),
            key=f"orphan_note_block_target_{selected_orphan_id}",
        )
        plan = build_orphan_note_block_repair_plan(selected_orphan_id, selected_target_id)
        st.write(f"Reattach status: `{plan['status']}`")
        st.write(plan["message"])
        reattach_confirmed = st.checkbox(
            "I understand this appends orphan blocks to the selected paper.",
            key=f"orphan_note_block_reattach_confirm_{selected_orphan_id}",
            disabled=not bool(plan["can_reattach"]),
        )
        if st.button(
            "Reattach orphan note blocks",
            key=f"orphan_note_block_reattach_apply_{selected_orphan_id}",
            disabled=not reattach_confirmed or not bool(plan["can_reattach"]),
        ):
            try:
                result = reattach_orphan_note_blocks(selected_orphan_id, selected_target_id, confirm=True)
            except OrphanRepairError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("library_health_report", None)
                st.session_state["library_health_repair_success"] = result["message"]
                st.rerun()
    with st.expander("Delete orphan note blocks"):
        st.warning("Delete is permanent. Export first if these blocks may be needed later.")
        delete_confirmed = st.checkbox(
            "I understand this deletes only the orphan note-block file.",
            key=f"orphan_note_block_delete_confirm_{selected_orphan_id}",
        )
        if st.button(
            "Delete orphan note blocks",
            key=f"orphan_note_block_delete_apply_{selected_orphan_id}",
            disabled=not delete_confirmed,
        ):
            try:
                result = delete_orphan_note_blocks(selected_orphan_id, confirm=True)
            except OrphanRepairError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("library_health_report", None)
                st.session_state["library_health_repair_success"] = result["message"]
                st.rerun()


def _render_orphan_project_link_repair(items: list[dict[str, object]]) -> None:
    st.caption(ORPHAN_EXPORT_ACTION)
    st.dataframe(pd.DataFrame(items), width="stretch", hide_index=True)
    link_ids = [str(item.get("link_id", "")) for item in items if item.get("link_id")]
    if not link_ids:
        return
    labels = {
        str(item.get("link_id", "")): (
            f"{item.get('reason', 'orphan')} - "
            f"{item.get('target_type', '')}:{item.get('target_id', '')}"
        )
        for item in items
        if item.get("link_id")
    }
    selected_link_id = st.selectbox(
        "Orphan project link",
        options=link_ids,
        format_func=lambda link_id: labels.get(link_id, link_id),
        key="orphan_project_link_selected_id",
    )
    selected_item = next((item for item in items if str(item.get("link_id", "")) == selected_link_id), {})
    if st.button("Export orphan project link", key=f"orphan_project_link_export_{selected_link_id}"):
        try:
            result = export_orphan_project_link(selected_link_id)
        except OrphanProjectLinkRepairError as exc:
            st.error(str(exc))
        else:
            st.success(result["message"])
            st.caption(result["export_path"])

    target_labels = _indexed_paper_labels()
    if target_labels:
        selected_target_id = st.selectbox(
            "Reattach link to paper",
            options=list(target_labels),
            format_func=lambda paper_id: target_labels.get(paper_id, paper_id),
            key=f"orphan_project_link_target_{selected_link_id}",
        )
        target_block_id = ""
        if selected_item.get("target_type") == "note_block":
            target_block_id = st.text_input(
                "Target note-block id",
                key=f"orphan_project_link_target_block_{selected_link_id}",
            )
        reattach_plan = build_orphan_project_link_reattach_plan(
            selected_link_id,
            selected_target_id,
            target_block_id=target_block_id,
        )
        st.write(f"Reattach status: `{reattach_plan['status']}`")
        st.write(reattach_plan["message"])
        reattach_confirmed = st.checkbox(
            "I understand this updates only the broken project link association.",
            key=f"orphan_project_link_reattach_confirm_{selected_link_id}",
            disabled=not bool(reattach_plan["can_reattach"]),
        )
        if st.button(
            "Reattach orphan project link",
            key=f"orphan_project_link_reattach_apply_{selected_link_id}",
            disabled=not reattach_confirmed or not bool(reattach_plan["can_reattach"]),
        ):
            try:
                result = reattach_orphan_project_link(
                    selected_link_id,
                    selected_target_id,
                    target_block_id=target_block_id,
                    confirm=True,
                )
            except OrphanProjectLinkRepairError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("library_health_report", None)
                st.session_state["library_health_repair_success"] = result["message"]
                st.rerun()

    plan = build_orphan_project_link_removal_plan(selected_link_id)
    st.write(f"Unlink status: `{plan['status']}`")
    st.write(plan["message"])
    st.code(
        "\n".join(
            [
                f"link_id: {plan.get('link_id', '')}",
                f"project_id: {plan.get('project_id', '')}",
                f"target: {plan.get('target_type', '')}:{plan.get('target_id', '')}",
                f"paper_id: {plan.get('paper_id', '')}",
                f"reason: {plan.get('reason', '')}",
                f"removes: {plan.get('removes', '')}",
            ]
        )
    )
    remove_confirmed = st.checkbox(
        "I understand this unlinks only the project link and leaves papers, PDFs, notes, note blocks, and index rows untouched.",
        key=f"orphan_project_link_remove_confirm_{selected_link_id}",
        disabled=not bool(plan["can_remove"]),
    )
    if st.button(
        "Unlink orphan project link",
        key=f"orphan_project_link_remove_apply_{selected_link_id}",
        disabled=not remove_confirmed or not bool(plan["can_remove"]),
    ):
        try:
            result = unlink_orphan_project_link(selected_link_id, confirm=True)
        except OrphanProjectLinkRepairError as exc:
            st.error(str(exc))
        else:
            st.session_state.pop("library_health_report", None)
            st.session_state["library_health_repair_success"] = result["message"]
            st.rerun()


def _render_missing_pdf_repair(items: list[dict[str, object]]) -> None:
    st.dataframe(pd.DataFrame(items), width="stretch", hide_index=True)
    dataframe = _index()
    missing_ids = [str(item.get("paper_id", "")) for item in items if item.get("paper_id")]
    if dataframe.empty or not missing_ids:
        return

    labels: dict[str, str] = {}
    for paper_id in missing_ids:
        matches = dataframe[dataframe["paper_id"] == paper_id]
        if matches.empty:
            labels[paper_id] = paper_id
            continue
        record = matches.iloc[0]
        labels[paper_id] = f"{record.get('title', '') or record.get('filename', '') or paper_id} ({paper_id})"

    selected_paper_id = st.selectbox(
        "Missing PDF record",
        options=missing_ids,
        format_func=lambda paper_id: labels.get(paper_id, paper_id),
        key="missing_pdf_repair_selected_id",
    )
    selected_record = dataframe[dataframe["paper_id"] == selected_paper_id].iloc[0].to_dict()
    st.code(
        "\n".join(
            [
                f"paper_id: {selected_paper_id}",
                f"missing filepath: {selected_record.get('filepath', '')}",
                f"stored pdf_sha256: {selected_record.get('pdf_sha256', '') or 'unavailable'}",
            ]
        )
    )

    candidates = list_reconnect_candidates(selected_record)
    reconnectable_candidates = [candidate for candidate in candidates if candidate["can_reconnect"]]
    if reconnectable_candidates:
        candidate_labels = {
            candidate["path"]: f"{candidate['filename']} - {candidate['status']}"
            for candidate in reconnectable_candidates
        }
        selected_target = st.selectbox(
            "Reconnect target in papers/",
            options=list(candidate_labels),
            format_func=lambda path: candidate_labels.get(path, path),
            key=f"missing_pdf_reconnect_target_{selected_paper_id}",
        )
        plan = build_reconnect_plan(selected_paper_id, selected_target)
        st.write(f"Reconnect status: `{plan['status']}`")
        st.write(plan["message"])
        st.code(
            "\n".join(
                [
                    f"Current: {plan['current_filepath']}",
                    f"Target:  {plan['target_path']}",
                    f"Expected SHA-256: {plan['current_pdf_sha256'] or 'unavailable'}",
                    f"Target SHA-256:   {plan['target_pdf_sha256'] or 'unavailable'}",
                ]
            )
        )
        mismatch_confirmed = True
        if plan["requires_hash_mismatch_confirmation"]:
            st.warning("The selected PDF content differs from the stored hash for this paper.")
            mismatch_confirmed = st.checkbox(
                "I understand this replacement PDF has a different SHA-256.",
                key=f"missing_pdf_hash_mismatch_confirm_{selected_paper_id}",
            )
            reconnect_confirmed = st.checkbox(
                "I understand reconnect updates only file identity fields.",
                key=f"missing_pdf_reconnect_confirm_{selected_paper_id}",
                disabled=not bool(plan["can_reconnect"]),
            )
        if st.button(
            "Reconnect PDF",
            key=f"missing_pdf_reconnect_apply_{selected_paper_id}",
            disabled=not reconnect_confirmed or not mismatch_confirmed or not bool(plan["can_reconnect"]),
        ):
            try:
                result = reconnect_missing_pdf(
                    selected_paper_id,
                    selected_target,
                    confirm_hash_mismatch=bool(mismatch_confirmed),
                )
            except MissingPDFRepairError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("library_health_report", None)
                st.session_state["library_health_repair_success"] = result["message"]
                st.rerun()
    else:
        st.info("No reconnectable PDFs were found inside papers/.")

    with st.expander("Other missing-PDF actions"):
        remove_confirmed = st.checkbox(
            "I understand this removes only the paper_index.csv row and leaves all files untouched.",
            key=f"missing_pdf_remove_confirm_{selected_paper_id}",
        )
        if st.button(
            "Remove from index",
            key=f"missing_pdf_remove_apply_{selected_paper_id}",
            disabled=not remove_confirmed,
        ):
            try:
                result = remove_missing_pdf_from_index(selected_paper_id, confirm=True)
            except MissingPDFRepairError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("library_health_report", None)
                st.session_state["library_health_repair_success"] = result["message"]
                st.rerun()
        if st.button("Keep missing", key=f"missing_pdf_keep_{selected_paper_id}"):
            st.info("No changes were made.")
        if st.button("Archive missing record", key=f"missing_pdf_archive_{selected_paper_id}"):
            set_paper_archived(selected_paper_id, True)
            _refresh_health_after_action("Missing-PDF record archived. No files or linked data were changed.")
            st.rerun()


def _render_pdf_inbox() -> None:
    st.subheader("Drive Inbox Import")
    st.write(
        "Treat a Google Drive for desktop folder as an import inbox. PDFs become managed papers only "
        "after they are copied into papers/ and processed by the existing library scanner."
    )
    success = st.session_state.pop("pdf_inbox_success", None)
    if success:
        st.success(success["message"])
        st.info(
            "The library index is updated. Next, open the paper from Library, enrich its metadata, "
            "and use Paper File Hygiene when the metadata is ready."
        )

    configured_path = get_inbox_path()
    inbox_value = st.text_input(
        "Inbox folder",
        value=str(configured_path or ""),
        key="pdf_inbox_path",
        help="BLUEPRINT_INBOX_DIR takes precedence when it is set.",
    )
    inbox_path = get_inbox_path(inbox_value)
    st.caption(f"Resolved inbox: {inbox_path or 'not configured'}")

    if st.button("Scan inbox", key="pdf_inbox_scan"):
        with st.status("Scanning inbox PDFs...", expanded=False) as status:
            st.session_state["pdf_inbox_scan_result"] = scan_pdf_inbox(inbox_path)
            status.update(label="Inbox scan complete.", state="complete")
        st.session_state.pop("pdf_inbox_preview", None)
        st.session_state["pdf_inbox_confirm"] = False

    scan_result = st.session_state.get("pdf_inbox_scan_result")
    if not scan_result:
        return
    if scan_result["status"] != "ok":
        st.warning(scan_result["message"])
        return

    candidates = scan_result["candidates"]
    st.write(scan_result["message"])
    if not candidates:
        st.info("No PDF files were found in the configured inbox folder.")
        return
    st.dataframe(
        pd.DataFrame(candidates)[["filename", "size_bytes", "modified_time", "status", "message"]],
        width="stretch",
        hide_index=True,
    )
    labels = {
        candidate["source_path"]: f"{candidate['filename']} - {candidate['status']}"
        for candidate in candidates
    }
    selected_source = st.selectbox(
        "Inbox PDF",
        options=list(labels),
        format_func=lambda path: labels.get(path, path),
        key="pdf_inbox_selected_source",
    )
    if st.button("Preview import", key="pdf_inbox_preview_button"):
        st.session_state["pdf_inbox_preview"] = build_inbox_import_plan(
            selected_source,
            inbox_path,
        )
        st.session_state["pdf_inbox_confirm"] = False

    preview = st.session_state.get("pdf_inbox_preview")
    if not preview or preview.get("source_path") != selected_source:
        return
    st.write(f"Status: `{preview['status']}`")
    st.write(preview["message"])
    st.code(f"Source: {preview['source_path']}\nTarget: {preview['target_path']}")
    confirmation = st.checkbox(
        "I understand this copies the selected PDF into papers/ and leaves the inbox source untouched.",
        key="pdf_inbox_confirm",
        disabled=not bool(preview["can_import"]),
    )
    if st.button(
        "Import selected PDF",
        key="pdf_inbox_import_button",
        disabled=not confirmation or not bool(preview["can_import"]),
    ):
        try:
            with st.status("Importing PDF...", expanded=False) as status:
                result = import_pdf_from_inbox(selected_source, inbox_path)
                status.update(label="PDF imported.", state="complete")
        except PDFInboxError as exc:
            st.error(str(exc))
            if exc.plan:
                st.session_state["pdf_inbox_preview"] = exc.plan
        else:
            st.session_state.pop("pdf_inbox_scan_result", None)
            st.session_state.pop("pdf_inbox_preview", None)
            st.session_state["pdf_inbox_success"] = result
            st.rerun()


def _render_paper_file_hygiene() -> None:
    st.subheader("Paper Hygiene")
    st.write(
        "Preview a human-readable PDF filename, then confirm one rename at a time. "
        "Scanning never renames files, and paper IDs remain unchanged."
    )
    success_message = st.session_state.pop("paper_file_hygiene_success", "")
    if success_message:
        st.success(success_message)

    dataframe = _index()
    if dataframe.empty:
        st.info("No indexed papers are available for filename review.")
        return

    labels = {
        str(row.paper_id): f"{row.title or row.filename or 'Untitled'} ({row.filename})"
        for row in dataframe.itertuples(index=False)
    }
    selected_paper_id = st.selectbox(
        "Paper",
        options=list(labels),
        format_func=lambda paper_id: labels.get(paper_id, paper_id),
        key="paper_file_hygiene_selected_id",
    )
    confirmation_key = f"paper_file_hygiene_confirm_{selected_paper_id}"
    if st.button("Preview", key="paper_file_hygiene_preview_button"):
        record = dataframe[dataframe["paper_id"] == selected_paper_id].iloc[0].to_dict()
        st.session_state["paper_file_hygiene_preview"] = build_rename_plan(record)
        st.session_state[confirmation_key] = False

    plan = st.session_state.get("paper_file_hygiene_preview")
    if not plan or plan.get("paper_id") != selected_paper_id:
        return

    col1, col2, col3 = st.columns([2, 2, 1])
    col1.write(f"Current filename: `{plan['current_filename']}`")
    col2.write(f"Recommended filename: `{plan['recommended_filename']}`")
    col3.write(f"Status: `{plan['status']}`")
    for warning in plan["warnings"]:
        st.warning(warning)
    if plan["status"] == "insufficient_metadata":
        st.info("Fill metadata first, then preview the filename again.")

    st.write("Planned paths")
    st.code(f"Current: {plan['current_path']}\nTarget:  {plan['target_path']}")
    confirmation = st.checkbox(
        "I understand this will rename the PDF file and update paper_index.csv.",
        key=confirmation_key,
        disabled=not bool(plan["can_apply"]),
    )
    if st.button(
        "Apply rename",
        key="paper_file_hygiene_apply_button",
        disabled=not confirmation or not bool(plan["can_apply"]),
    ):
        try:
            result = apply_paper_file_rename(selected_paper_id)
        except PaperFileHygieneError as exc:
            st.error(str(exc))
            if exc.plan:
                st.session_state["paper_file_hygiene_preview"] = exc.plan
        else:
            st.session_state.pop("paper_file_hygiene_preview", None)
            st.session_state["paper_file_hygiene_success"] = (
                f"Renamed PDF to {result['recommended_filename']} without changing paper_id."
            )
            st.rerun()


def run() -> None:
    ensure_workspace_dirs()
    st.set_page_config(page_title="BluePrintReboot", layout="wide")

    pages = navigation_pages()
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

    try:
        pages[st.session_state["current_page"]]()
    except JsonStoreError as exc:
        st.error("A local JSON store could not be read. No changes were made.")
        st.warning(exc.suggested_action)
        with st.expander("Storage error details"):
            st.write(f"Path: `{exc.path}`")
            st.write(f"Issue: {exc.summary}")
            st.write(f"Exception: `{exc.__class__.__name__}`")


def navigation_pages() -> dict[str, Callable[[], None]]:
    return {
        "Dashboard": dashboard_page,
        "Library": library_page,
        "Paper Detail": paper_detail_page,
        "Project Workspace": render_project_workspace,
        "Tag Manager": render_tag_manager_page,
        "Settings": settings_page,
    }
