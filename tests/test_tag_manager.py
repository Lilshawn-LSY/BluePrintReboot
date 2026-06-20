import json

import pandas as pd
import pytest

from ingest.tag_suggester import load_canonical_tags
from services.tag_governance import (
    apply_used_tag_merge_to_index,
    create_canonical_tag,
    filter_used_tags,
    load_tag_manager_records,
    preview_used_tag_merge,
    register_tag_alias,
    summarize_used_tags,
)
from storage.index_store import load_index, save_index
from tests.helpers import make_workspace


def _registry() -> dict:
    return {
        "known-tag": {
            "label": "Known Tag",
            "category": "concept",
            "aliases": ["legacy tag"],
            "status": "active",
        },
        "other-tag": {
            "label": "Other Tag",
            "category": "method",
            "aliases": [],
            "status": "active",
        },
    }


def _write_registry(path, registry: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry or _registry()), encoding="utf-8")


def test_used_tag_summary_counts_papers_and_classifies_status() -> None:
    records = [
        {"paper_id": "p1", "title": "One", "tags": "known-tag, legacy tag, custom, lr"},
        {"paper_id": "p2", "title": "Two", "tags": "custom; legacy-tag"},
    ]

    summaries = summarize_used_tags(records, _registry())
    by_tag = {item["normalized_tag"]: item for item in summaries}

    assert by_tag["known-tag"]["status"] == "canonical"
    assert by_tag["legacy-tag"]["status"] == "alias-resolved"
    assert by_tag["legacy-tag"]["category"] == "concept"
    assert by_tag["custom"]["status"] == "unknown"
    assert by_tag["custom"]["paper_count"] == 2
    assert [example["title"] for example in by_tag["custom"]["paper_examples"]] == ["One", "Two"]


def test_used_tag_summary_marks_short_and_ambiguous_tags() -> None:
    registry = _registry() | {
        "first": {"label": "First", "category": "concept", "aliases": ["shared"], "status": "active"},
        "second": {"label": "Second", "category": "concept", "aliases": ["shared"], "status": "active"},
    }

    by_tag = {
        item["normalized_tag"]: item
        for item in summarize_used_tags([{"paper_id": "p1", "tags": "lr, shared"}], registry)
    }

    assert by_tag["lr"]["is_short"] is True
    assert "explicit review" in by_tag["lr"]["warning"]
    assert by_tag["shared"]["status"] == "unknown"
    assert by_tag["shared"]["is_ambiguous"] is True
    assert "first, second" in by_tag["shared"]["warning"]


def test_unknown_and_warning_filters() -> None:
    summaries = summarize_used_tags(
        [{"paper_id": "p1", "tags": "known-tag, custom, lr"}],
        _registry(),
    )

    assert {item["normalized_tag"] for item in filter_used_tags(summaries, "unknown")} == {"custom", "lr"}
    assert [item["normalized_tag"] for item in filter_used_tags(summaries, "canonical")] == ["known-tag"]
    assert [item["normalized_tag"] for item in filter_used_tags(summaries, "ambiguous/short")] == ["lr"]


def test_used_tag_merge_preview_is_exact_and_does_not_mutate_records() -> None:
    records = [{"paper_id": "p1", "tags": "legacy tag, known-tag, keep-me"}]

    preview = preview_used_tag_merge(records, "legacy-tag", "other-tag", _registry())

    assert records[0]["tags"] == "legacy tag, known-tag, keep-me"
    assert preview["affected_records"] == 1
    assert preview["changes"][0]["after"] == "other-tag, known-tag, keep-me"


def test_used_tag_merge_apply_updates_index_and_deduplicates() -> None:
    workspace = make_workspace("tag-manager-merge")
    index_csv = workspace / "data" / "paper_index.csv"
    save_index(
        pd.DataFrame(
            [
                {"paper_id": "p1", "filename": "One.pdf", "title": "One", "tags": "legacy tag, known-tag, keep-me"},
                {"paper_id": "p2", "filename": "Two.pdf", "title": "Two", "tags": "untouched; untouched"},
            ]
        ),
        index_csv,
    )

    result = apply_used_tag_merge_to_index("legacy-tag", "known-tag", _registry(), index_csv)
    updated = load_index(index_csv)

    assert result["affected_records"] == 1
    assert updated.loc[updated["paper_id"] == "p1", "tags"].iloc[0] == "known-tag, keep-me"
    assert updated.loc[updated["paper_id"] == "p2", "tags"].iloc[0] == "untouched; untouched"


def test_register_tag_alias_updates_registry_without_touching_library() -> None:
    workspace = make_workspace("tag-manager-alias")
    registry_path = workspace / "config" / "canonical_tags.json"
    index_csv = workspace / "data" / "paper_index.csv"
    _write_registry(registry_path)
    save_index(pd.DataFrame([{"paper_id": "p1", "filename": "One.pdf", "tags": "new alias"}]), index_csv)
    before_index = index_csv.read_bytes()

    register_tag_alias("new alias", "known-tag", registry_path)

    assert "new alias" in load_canonical_tags(registry_path)["known-tag"]["aliases"]
    assert index_csv.read_bytes() == before_index


def test_register_tag_alias_rejects_collisions() -> None:
    workspace = make_workspace("tag-manager-alias-collision")
    registry_path = workspace / "canonical_tags.json"
    _write_registry(registry_path)

    with pytest.raises(ValueError, match="collides"):
        register_tag_alias("Known Tag", "other-tag", registry_path)


def test_create_canonical_tag_uses_selected_tag_as_alias() -> None:
    workspace = make_workspace("tag-manager-create")
    registry_path = workspace / "canonical_tags.json"
    _write_registry(registry_path)

    create_canonical_tag("legacy-custom", "Custom Concept", "concept", registry_path)
    registry = load_canonical_tags(registry_path)

    assert registry["custom-concept"] == {
        "label": "Custom Concept",
        "category": "concept",
        "aliases": ["legacy-custom"],
        "status": "active",
    }


def test_loading_tag_manager_data_does_not_rewrite_index_or_registry() -> None:
    workspace = make_workspace("tag-manager-read-only")
    index_csv = workspace / "data" / "paper_index.csv"
    registry_path = workspace / "config" / "canonical_tags.json"
    save_index(pd.DataFrame([{"paper_id": "p1", "filename": "One.pdf", "tags": "legacy tag"}]), index_csv)
    _write_registry(registry_path)
    before_index = index_csv.read_bytes()
    before_registry = registry_path.read_bytes()

    records = load_tag_manager_records(index_csv)
    summarize_used_tags(records, load_canonical_tags(registry_path))

    assert index_csv.read_bytes() == before_index
    assert registry_path.read_bytes() == before_registry
