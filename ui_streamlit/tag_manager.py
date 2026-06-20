from __future__ import annotations

import pandas as pd
import streamlit as st

from ingest.tag_suggester import load_canonical_tags
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
        use_container_width=True,
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
            st.write(f"Affected papers: **{preview['affected_records']}**")
            for change in preview["changes"][:5]:
                st.code(f"Before: {change['before']}\nAfter:  {change['after']}")
            confirmed = st.checkbox(
                "I reviewed this preview and want to update paper_index.csv.",
                key=f"tag_manager_merge_confirm_{selected['normalized_tag']}_{target}",
            )
            if st.button(
                "Apply tag merge",
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
                "Register alias",
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
            "Create canonical tag",
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
