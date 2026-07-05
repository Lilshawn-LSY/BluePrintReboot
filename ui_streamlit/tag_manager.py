from __future__ import annotations

import pandas as pd
import streamlit as st

from ingest.tag_suggester import load_canonical_tags
from services.tag_book import (
    CATEGORY_VALUES,
    load_tag_book,
    preview_near_duplicate_tags,
    validate_tag_book,
)
from services.tag_governance import (
    CANONICAL_TAG_CATEGORIES,
    TAG_MANAGER_FILTERS,
    apply_used_tag_merge_to_index,
    create_canonical_tag,
    filter_used_tags,
    load_tag_manager_records,
    preview_used_tag_merge,
    register_tag_alias,
    summarize_used_tags,
)


def render_tag_manager_page() -> None:
    st.title("Tag Manager")
    st.write(
        "Review the tags currently used by your library. Registry and library changes happen only "
        "after you choose an action explicitly."
    )

    records = load_tag_manager_records()
    registry = load_canonical_tags()
    tag_book = load_tag_book()
    _render_tag_book_panel(tag_book)
    summaries = summarize_used_tags(records, registry)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Used tags", len(summaries))
    metric_columns[1].metric("Canonical", _count_status(summaries, "canonical"))
    metric_columns[2].metric("Alias-resolved", _count_status(summaries, "alias-resolved"))
    metric_columns[3].metric("Unknown", _count_status(summaries, "unknown"))

    if not summaries:
        st.info("No library tags are currently in use.")
        return

    selected_filter = st.selectbox("Filter tags", TAG_MANAGER_FILTERS)
    filtered = filter_used_tags(summaries, selected_filter)
    if not filtered:
        st.info("No used tags match this filter.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Tag": item["tag"],
                    "Papers": item["paper_count"],
                    "Status": item["status"],
                    "Category": item["category"],
                    "Warning": item["warning"],
                }
                for item in filtered
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    selected_normalized = st.selectbox(
        "Select a used tag",
        [item["normalized_tag"] for item in filtered],
        format_func=lambda value: _tag_option_label(value, filtered),
    )
    selected = next(item for item in filtered if item["normalized_tag"] == selected_normalized)
    _render_tag_detail(selected)
    _render_tag_actions(selected, records, registry)


def _render_tag_book_panel(tag_book: dict) -> None:
    with st.expander("Tag Book", expanded=True):
        tags = list(tag_book.get("tags", {}).values())
        warnings = validate_tag_book(tag_book)
        near_duplicates = preview_near_duplicate_tags(tag_book)
        metric_columns = st.columns(3)
        metric_columns[0].metric("Canonical tags", len(tags))
        metric_columns[1].metric("Validation warnings", len(warnings))
        metric_columns[2].metric("Near-duplicate previews", len(near_duplicates))

        filters = st.columns([2, 2, 3])
        category_options = ("all",) + CATEGORY_VALUES
        category = filters[0].selectbox("Category", category_options, key="tag_book_category_filter")
        statuses = tuple(sorted({str(tag.get("status", "active") or "active") for tag in tags}))
        status = filters[1].selectbox("Status", ("all",) + statuses, key="tag_book_status_filter")
        search = filters[2].text_input("Search Tag Book", key="tag_book_search")

        filtered = _filter_tag_book_entries(tags, category, status, search)
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Canonical": tag["canonical"],
                        "Label": tag.get("label", ""),
                        "Category": tag.get("category", ""),
                        "Status": tag.get("status", ""),
                        "Aliases": ", ".join(tag.get("aliases", [])),
                    }
                    for tag in filtered
                ]
            ),
            width="stretch",
            hide_index=True,
        )

        if warnings:
            with st.expander("Validation warnings"):
                for warning in warnings:
                    st.write(f"- {warning}")
        if near_duplicates:
            with st.expander("Near-duplicate preview"):
                for item in near_duplicates[:20]:
                    st.write(
                        f"`{item['left']}` ~ `{item['right']}` "
                        f"({item['similarity']}) - {item['reason']}"
                    )


def _filter_tag_book_entries(tags: list[dict], category: str, status: str, search: str) -> list[dict]:
    needle = str(search or "").strip().lower()
    filtered: list[dict] = []
    for tag in tags:
        if category != "all" and tag.get("category") != category:
            continue
        if status != "all" and str(tag.get("status", "active") or "active") != status:
            continue
        haystack = " ".join(
            [
                str(tag.get("canonical", "")),
                str(tag.get("label", "")),
                str(tag.get("category", "")),
                " ".join(str(alias) for alias in tag.get("aliases", [])),
            ]
        ).lower()
        if needle and needle not in haystack:
            continue
        filtered.append(tag)
    return sorted(filtered, key=lambda item: str(item.get("canonical", "")))


def _render_tag_detail(selected: dict) -> None:
    st.subheader("Selected Tag")
    detail_columns = st.columns(3)
    detail_columns[0].write(f"**Normalized:** `{selected['normalized_tag']}`")
    detail_columns[1].write(f"**Status:** {selected['status']}")
    detail_columns[2].write(f"**Papers:** {selected['paper_count']}")
    if selected["category"]:
        st.write(f"Category: `{selected['category']}`")
    if selected["canonical_tag"] and selected["status"] == "alias-resolved":
        st.write(f"Resolves to: `{selected['canonical_tag']}`")
    if selected["warning"]:
        st.warning(selected["warning"])

    st.write("Affected paper examples")
    for example in selected["paper_examples"]:
        label = example["title"] or example["paper_id"] or "Untitled paper"
        st.write(f"- {label}")


def _render_tag_actions(selected: dict, records: list[dict], registry: dict) -> None:
    st.subheader("Possible Actions")
    canonical_options = sorted(registry)
    if not canonical_options:
        st.info("Create a canonical tag before merging or registering aliases.")

    with st.expander("Merge into an existing canonical tag"):
        if canonical_options:
            target = st.selectbox(
                "Merge target",
                canonical_options,
                format_func=lambda tag: _canonical_option_label(tag, registry),
                key="tag_manager_merge_target",
            )
            preview = preview_used_tag_merge(
                records,
                selected["normalized_tag"],
                target,
                registry,
            )
            st.write("**Preview**")
            st.write(f"Affected papers: **{preview['affected_records']}**")
            for change in preview["changes"][:5]:
                st.code(f"Before: {change['before']}\nAfter:  {change['after']}")
            confirmed = st.checkbox(
                "I reviewed this preview and want to update paper_index.csv.",
                key=f"tag_manager_merge_confirm_{selected['normalized_tag']}_{target}",
            )
            if st.button(
                "Apply",
                disabled=not confirmed or not preview["affected_records"],
                key=f"tag_manager_merge_apply_{selected['normalized_tag']}_{target}",
            ):
                result = apply_used_tag_merge_to_index(
                    selected["normalized_tag"],
                    target,
                    registry,
                )
                st.success(f"Updated {result['affected_records']} paper(s).")
                st.rerun()

    with st.expander("Register as an alias"):
        if canonical_options:
            target = st.selectbox(
                "Canonical tag",
                canonical_options,
                format_func=lambda tag: _canonical_option_label(tag, registry),
                key="tag_manager_alias_target",
            )
            st.caption("This updates the canonical registry only. Library tags are not rewritten.")
            if st.button(
                "Save alias",
                key=f"tag_manager_alias_apply_{selected['normalized_tag']}",
            ):
                try:
                    register_tag_alias(selected["tag"], target)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.success(f"Registered `{selected['tag']}` as an alias of `{target}`.")
                    st.rerun()

    with st.expander("Create a canonical tag"):
        label = st.text_input(
            "Label",
            value=_default_label(selected["tag"]),
            key=f"tag_manager_create_label_{selected['normalized_tag']}",
        )
        category = st.selectbox(
            "Category",
            CANONICAL_TAG_CATEGORIES,
            key=f"tag_manager_create_category_{selected['normalized_tag']}",
        )
        st.caption("The selected library tag will be included as an alias. Existing papers are unchanged.")
        if st.button(
            "Create",
            key=f"tag_manager_create_apply_{selected['normalized_tag']}",
        ):
            try:
                create_canonical_tag(selected["tag"], label, category)
            except ValueError as error:
                st.error(str(error))
            else:
                st.success(f"Created canonical tag `{label}`.")
                st.rerun()


def _count_status(summaries: list[dict], status: str) -> int:
    return sum(item["status"] == status for item in summaries)


def _tag_option_label(normalized_tag: str, summaries: list[dict]) -> str:
    item = next(summary for summary in summaries if summary["normalized_tag"] == normalized_tag)
    return f"{item['tag']} ({item['paper_count']} papers, {item['status']})"


def _canonical_option_label(tag: str, registry: dict) -> str:
    entry = registry[tag]
    return f"{entry.get('label', tag)} [{tag}]"


def _default_label(tag: str) -> str:
    return " ".join(part.capitalize() for part in str(tag).replace("_", "-").split("-") if part)
