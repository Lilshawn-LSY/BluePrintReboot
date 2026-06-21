from pathlib import Path
from typing import Callable

import pandas as pd
import streamlit as st

from ingest.crossref import (
    CrossrefLookupError,
    check_crossref_connectivity,
    fetch_crossref_by_doi,
    parse_crossref_work,
    proxy_environment,
)
from ingest.document_text import get_text_extraction_backends
from ingest.doi import is_probable_doi, normalize_doi
from ingest.scanner import extract_doi_metadata_from_pdf
from ingest.tag_suggester import (
    DEFAULT_CANONICAL_TAG_PATH,
    DEFAULT_RULE_PATH,
    audit_canonical_tags,
    build_tag_suggestion_record,
    explain_tag_suggestions,
    load_canonical_tags,
    load_tag_rules,
    merge_tags,
    suggest_tags,
    validate_tag_rules,
)
from services.paper_file_hygiene import (
    PaperFileHygieneError,
    apply_paper_file_rename,
    build_rename_plan,
)
from storage.index_store import (
    INDEX_COLUMNS,
    accept_crossref_metadata,
    load_index,
    update_index_from_scan,
    update_paper_metadata,
)
from storage.paths import DATA_DIR, EXPORTS_DIR, INDEX_CSV, NOTES_DIR, PAPERS_DIR, ensure_workspace_dirs
from ui_streamlit.project_workspace import render_paper_project_links, render_project_workspace
from ui_streamlit.reader_workspace import render_reader_workspace
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
            st.success("Metadata saved.")
            st.rerun()

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

    if st.button("Enrich Metadata", type="primary"):
        normalized_current_doi = normalize_doi(current_doi)
        if normalized_current_doi:
            detected_doi = ""
            extraction_source = "none"
            saved = False
            message = "Existing DOI used; PDF extraction was not needed."
        else:
            result = extract_doi_metadata_from_pdf(Path(record["filepath"]))
            detected_doi = result.doi
            extraction_source = result.source
            saved = False
            message = ""
            if detected_doi:
                update_paper_metadata(
                    record["paper_id"],
                    {
                        "doi": detected_doi,
                        "doi_source": extraction_source,
                        "extraction_source": extraction_source,
                        "extraction_checked_at": _now_iso(),
                    },
                )
                saved = True
                message = "Detected DOI was saved to this paper."
            else:
                message = "No DOI detected. You can paste one manually."

        if normalized_current_doi:
            saved = False
        elif detected_doi:
            saved = True

        if detected_doi and normalized_current_doi and detected_doi == normalized_current_doi:
            message = "Detected DOI already matches the saved DOI."
        elif detected_doi and normalized_current_doi:
            message = "Detected DOI was not saved because this paper already has a DOI."

        st.session_state[extraction_key] = {
            "doi": detected_doi,
            "source": extraction_source,
            "saved": saved,
            "message": message,
        }

        doi_for_lookup = detected_doi or normalized_current_doi
        crossref_status = "not attempted"
        if doi_for_lookup:
            try:
                crossref_message = fetch_crossref_by_doi(doi_for_lookup)
                st.session_state[preview_key] = parse_crossref_work(crossref_message)
                crossref_status = "metadata found; review the preview before accepting"
            except CrossrefLookupError as exc:
                crossref_status = f"failed: {exc}"
            except Exception as exc:
                crossref_status = f"failed: {exc}"
        elif not detected_doi:
            crossref_status = "not attempted; no DOI available"

        st.session_state[enrichment_key] = {
            "crossref_status": crossref_status,
        }
        if saved or crossref_status.startswith("metadata found"):
            st.rerun()

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
            st.write(f"Detected DOI: `{detected_doi}`")
            st.write(f"Extraction source: `{extraction.get('source', 'none')}`")
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
            st.write("Detected DOI: `not found`")
            st.write(f"DOI extraction source: `{extraction.get('source', 'none')}`")
            st.write("Saved to index: `no`")
            st.write(f"Crossref lookup status: `{enrichment.get('crossref_status', 'not attempted')}`")

    preview = st.session_state.get(preview_key)
    suggestion_record = build_tag_suggestion_record(record, form_values=form_values, crossref_preview=preview)
    suggestions = suggest_tags(suggestion_record)
    suggestion_details = explain_tag_suggestions(suggestion_record)
    st.write("Suggested tags")
    with st.expander("Tag suggestion input"):
        st.write(f"Title: `{suggestion_record.get('title', '')}`")
        st.write(f"Abstract length: `{len(str(suggestion_record.get('abstract', '') or ''))}`")
        st.write(f"Keywords: `{suggestion_record.get('keywords', '')}`")
        st.write(f"Journal: `{suggestion_record.get('journal', '')}`")
        st.write(f"Filename: `{suggestion_record.get('filename', '')}`")
        st.write(f"Crossref subjects: `{suggestion_record.get('crossref_subjects', '')}`")
        st.write(f"Existing tags: `{suggestion_record.get('tags', '')}`")
    if suggestions:
        for detail in suggestion_details:
            fields = "/".join(detail.get("matched_fields", []))
            st.caption(f"`{detail['tag']}` - matched {fields}")
        if st.button("Apply suggested tags"):
            merged_tags = merge_tags(record.get("tags", ""), suggestions)
            update_paper_metadata(record["paper_id"], {"tags": merged_tags})
            st.success("Suggested tags added.")
            st.rerun()
    else:
        st.caption("No new tag suggestions.")

    with st.expander("Advanced manual lookup"):
        if st.button("Lookup Crossref by DOI"):
            _lookup_crossref_by_current_doi(current_doi, preview_key)

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
                    "abstract",
                    "keywords",
                    "crossref_subjects",
                    "doi",
                    "metadata_source",
                    "metadata_confidence",
                )
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    if st.button("Apply Crossref metadata"):
        accept_crossref_metadata(record["paper_id"], preview)
        st.session_state.pop(preview_key, None)
        st.success("Crossref metadata accepted.")
        st.rerun()


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _lookup_crossref_by_current_doi(current_doi: str, preview_key: str) -> None:
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
    st.subheader("Extraction Backends")
    backends = get_text_extraction_backends()
    st.write(
        "PDF text extraction backends: "
        + ", ".join(f"{name}={'available' if available else 'unavailable'}" for name, available in backends.items())
    )
    st.subheader("Tag Rulebook")
    rules = load_tag_rules()
    canonical_registry = load_canonical_tags()
    validation_warnings = validate_tag_rules(rules)
    tag_audit = audit_canonical_tags(_index().to_dict("records"), canonical_registry)
    st.write(f"Rulebook path: `{DEFAULT_RULE_PATH}`")
    st.write(f"Suggestion rules: `{len(rules)}`")
    st.write(f"Canonical registry: `{DEFAULT_CANONICAL_TAG_PATH}`")
    st.write(f"Canonical tags: `{len(canonical_registry)}`")
    if validation_warnings:
        st.warning("Rulebook validation warnings:")
        for warning in validation_warnings:
            st.write(f"- {warning}")
    else:
        st.success("Rulebook validation passed.")
    st.write(f"Unknown library tags: `{len(tag_audit['unknown_tags'])}`")
    st.write(f"Unused canonical tags: `{len(tag_audit['unused_canonical_tags'])}`")
    st.write("Canonical alias collisions")
    if tag_audit["alias_collisions"]:
        for alias, owners in tag_audit["alias_collisions"].items():
            st.warning(f"`{alias}` maps to multiple tags: {', '.join(owners)}")
    else:
        st.write("None")
    st.caption("Use Tag Manager to review, merge, or register library tags.")
    _render_paper_file_hygiene()
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


def _render_paper_file_hygiene() -> None:
    st.subheader("Paper File Hygiene")
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

    pages[st.session_state["current_page"]]()


def navigation_pages() -> dict[str, Callable[[], None]]:
    return {
        "Dashboard": dashboard_page,
        "Library": library_page,
        "Paper Detail": paper_detail_page,
        "Project Workspace": render_project_workspace,
        "Tag Manager": render_tag_manager_page,
        "Settings": settings_page,
    }
