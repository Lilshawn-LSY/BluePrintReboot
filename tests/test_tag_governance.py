from copy import deepcopy

from ingest.tag_suggester import (
    apply_tag_merge_to_records,
    audit_canonical_tags,
    build_tag_alias_index,
    canonicalize_tags,
    load_canonical_tags,
    preview_tag_merge,
    resolve_canonical_tag,
    suggest_tags,
)


def test_load_canonical_tags_from_config() -> None:
    registry = load_canonical_tags()

    assert registry["synthetic-biology"] == {
        "label": "Synthetic Biology",
        "category": "field",
        "aliases": ["synthetic biology", "synthetic-biology"],
        "status": "active",
    }


def test_resolve_canonical_tag_accepts_aliases_and_labels() -> None:
    registry = load_canonical_tags()

    assert resolve_canonical_tag("Arabidopsis thaliana", registry) == "arabidopsis"
    assert resolve_canonical_tag("AI Biology", registry) == "ai-biology"
    assert resolve_canonical_tag("not-registered", registry) is None
    assert canonicalize_tags("AI Biology, custom tag, ai-biology", registry) == ["ai-biology", "custom-tag"]


def test_build_tag_alias_index_reports_ambiguous_aliases() -> None:
    registry = {
        "first": {"label": "First", "aliases": ["shared"], "category": "concept", "status": "active"},
        "second": {"label": "Second", "aliases": ["Shared"], "category": "concept", "status": "active"},
    }

    alias_index = build_tag_alias_index(registry)

    assert alias_index["collisions"] == {"shared": ["first", "second"]}
    assert "shared" not in alias_index["alias_to_canonical"]
    assert resolve_canonical_tag("shared", registry) is None


def test_canonical_audit_resolves_aliases_and_reports_unknown_and_unused_tags() -> None:
    registry = {
        "known-tag": {"label": "Known Tag", "aliases": ["known alias"], "category": "concept", "status": "active"},
        "unused-tag": {"label": "Unused Tag", "aliases": [], "category": "concept", "status": "active"},
    }

    audit = audit_canonical_tags(
        [{"tags": "known alias, known-tag, personal tag"}],
        registry,
    )

    assert audit["known_tags"] == ["known-tag"]
    assert audit["unknown_tags"] == ["personal-tag"]
    assert audit["unused_canonical_tags"] == ["unused-tag"]
    assert audit["duplicate_normalized_tags"] == ["known-tag"]


def test_preview_tag_merge_does_not_modify_records() -> None:
    registry = load_canonical_tags()
    records = [{"paper_id": "paper-1", "tags": "personal-tag, AI, protocol"}]
    original = deepcopy(records)

    preview = preview_tag_merge(records, "AI", "bioinformatics", registry)

    assert records == original
    assert preview["affected_records"] == 1
    assert preview["changes"][0]["before"] == "personal-tag, AI, protocol"
    assert preview["changes"][0]["after"] == "personal-tag, bioinformatics, protocol"


def test_apply_tag_merge_deduplicates_and_preserves_unrelated_tag_order() -> None:
    registry = load_canonical_tags()
    records = [
        {
            "paper_id": "paper-1",
            "title": "Paper",
            "tags": "first-personal, artificial intelligence, bioinformatics, AI Biology, last-personal",
        }
    ]

    merged = apply_tag_merge_to_records(records, "ai-biology", "bioinformatics", registry)

    assert merged[0]["tags"] == "first-personal, bioinformatics, last-personal"
    assert merged[0]["title"] == "Paper"
    assert records[0]["tags"] == "first-personal, artificial intelligence, bioinformatics, AI Biology, last-personal"


def test_apply_tag_merge_can_map_an_unknown_tag_to_a_canonical_tag() -> None:
    registry = load_canonical_tags()

    merged = apply_tag_merge_to_records(
        [{"tags": "legacy custom, protocol, legacy-custom"}],
        "legacy custom",
        "method",
        registry,
    )

    assert merged[0]["tags"] == "method, protocol"


def test_apply_tag_merge_leaves_unaffected_records_exactly_unchanged() -> None:
    registry = load_canonical_tags()
    records = [{"paper_id": "paper-2", "tags": "Personal Tag; personal-tag"}]

    merged = apply_tag_merge_to_records(records, "ai-biology", "method", registry)

    assert merged == records


def test_existing_tag_suggestion_behavior_remains_rulebook_driven() -> None:
    suggestions = suggest_tags(
        {
            "title": "Synthetic biology methods",
            "keywords": "scRNA-seq",
            "tags": "synthetic-biology",
        }
    )

    assert "synthetic-biology" not in suggestions
    assert "single-cell-rna-seq" in suggestions
