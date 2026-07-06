import json

from ingest.tag_suggester import load_canonical_tags, load_tag_rules
from services.tag_book import (
    extract_evidence_snippet,
    explain_tag_book_suggestions,
    group_suggestions_by_category,
    load_tag_book,
    normalize_tag,
    normalize_tag_with_rules,
    selected_suggestion_tag_values,
    suggestion_selection_id,
    tag_book_to_registry,
    validate_tag_book,
)
from tests.helpers import make_workspace


def test_tag_book_loads_default_files() -> None:
    tag_book = load_tag_book()
    registry = tag_book_to_registry(tag_book)

    assert "synthetic-biology" in tag_book["tags"]
    assert registry["synthetic-biology"]["aliases"] == ["synthetic biology", "synthetic-biology"]
    assert tag_book["method_lexicon"]
    assert tag_book["candidate_patterns"]


def test_tag_book_validation_passes_for_default_config() -> None:
    assert validate_tag_book(load_tag_book()) == []


def test_seed_cleanup_removes_generic_method_from_active_rules() -> None:
    rules = load_tag_rules()

    assert "method" not in rules
    assert validate_tag_book(load_tag_book()) == []


def test_alias_normalization_is_kebab_case() -> None:
    assert normalize_tag(" Single Cell RNA Seq ") == "single-cell-rna-seq"
    assert normalize_tag("sc RNA-seq") == "sc-rna-seq"


def test_normalization_rules_helper_uses_loaded_rules() -> None:
    rules = load_tag_book()["normalization_rules"]

    assert normalize_tag_with_rules("  AI_Biology!!! ", rules) == "ai-biology"
    assert normalize_tag_with_rules("  AI_Biology!!! ", rules | {"lowercase": False}) == "AI-Biology"


def test_duplicate_canonical_detection() -> None:
    tag_book = {
        "raw_tag_records": [
            {"canonical": "same-tag", "category": "concept", "aliases": ["same"], "status": "active"},
            {"canonical": "Same Tag", "category": "concept", "aliases": ["same tag"], "status": "active"},
        ],
        "tags": {},
        "blocked_terms": [],
    }

    warnings = validate_tag_book(tag_book)

    assert any("Duplicate canonical tag 'same-tag'" in warning for warning in warnings)


def test_alias_conflict_detection() -> None:
    tag_book = {
        "raw_tag_records": [
            {"canonical": "first", "category": "concept", "aliases": ["shared"], "status": "active"},
            {"canonical": "second", "category": "concept", "aliases": ["Shared"], "status": "active"},
        ],
        "tags": {},
        "blocked_terms": [],
    }

    warnings = validate_tag_book(tag_book)

    assert any("used by multiple canonical tags" in warning for warning in warnings)


def test_normalized_alias_conflict_detection() -> None:
    tag_book = {
        "raw_tag_records": [
            {
                "canonical": "first",
                "category": "concept",
                "aliases": ["shared alias"],
                "status": "active",
            },
            {
                "canonical": "second",
                "category": "concept",
                "aliases": ["shared-alias"],
                "status": "active",
            }
        ],
        "tags": {},
        "blocked_terms": [],
    }

    warnings = validate_tag_book(tag_book)

    assert any("Normalized alias 'shared-alias'" in warning for warning in warnings)


def test_known_canonical_suggestion_from_title_and_abstract() -> None:
    suggestions = explain_tag_book_suggestions(
        {
            "title": "Synthetic biology design principles",
            "abstract": "A synthetic biology system for cells.",
            "tags": "",
        }
    )
    synthetic = next(item for item in suggestions if item["canonical"] == "synthetic-biology")

    assert synthetic["kind"] == "known_canonical"
    assert synthetic["category"] == "field"
    assert synthetic["matched_fields"] == ["title", "abstract"]


def test_single_cell_rna_seq_does_not_match_generic_single_cell() -> None:
    suggestions = explain_tag_book_suggestions({"title": "A single cell atlas of roots", "tags": ""})

    assert "single-cell-rna-seq" not in {
        item["canonical"]
        for item in suggestions
        if item.get("kind") == "known_canonical"
    }


def test_lateral_root_matches_specific_alias() -> None:
    suggestions = explain_tag_book_suggestions({"abstract": "Lateral root emergence was measured.", "tags": ""})
    lateral = next(item for item in suggestions if item["canonical"] == "lateral-root")

    assert lateral["kind"] == "known_canonical"
    assert lateral["matched_text"] == "Lateral root"


def test_specific_root_suggestion_suppresses_generic_root_development() -> None:
    suggestions = explain_tag_book_suggestions({"abstract": "Lateral root development was reviewed.", "tags": ""})
    canonicals = {item["canonical"] for item in suggestions}

    assert "lateral-root" in canonicals
    assert "root-development" not in canonicals


def test_new_method_candidate_suggestion_from_lexicon() -> None:
    suggestions = explain_tag_book_suggestions(
        {"abstract": "We performed a genome-wide CRISPR screen in pooled cells.", "tags": ""}
    )
    crispr = next(item for item in suggestions if item["canonical"] == "crispr-screen")

    assert crispr["kind"] == "new_candidate"
    assert crispr["category"] == "method"
    assert crispr["matched_text"] in {"CRISPR screen", "genome-wide CRISPR screen"}


def test_blocked_term_suppression() -> None:
    tag_book = load_tag_book()
    tag_book["blocked_terms"] = ["crispr-screen"]

    suggestions = explain_tag_book_suggestions(
        {"abstract": "We performed a genome-wide CRISPR screen.", "tags": ""},
        tag_book,
    )

    assert "crispr-screen" not in {item["canonical"] for item in suggestions}


def test_evidence_bearing_suggestion_output() -> None:
    suggestions = explain_tag_book_suggestions(
        {"abstract": "The root samples were profiled by scRNA-seq before validation.", "tags": ""}
    )
    single_cell = next(item for item in suggestions if item["canonical"] == "single-cell-rna-seq")

    assert single_cell["display"] == "Single-cell RNA-seq"
    assert single_cell["source"] == "abstract"
    assert single_cell["matched_text"] == "scRNA-seq"
    assert single_cell["reason"]
    assert single_cell["evidence"][0]["source"] == "abstract"
    assert "root samples were profiled by scRNA-seq" in single_cell["evidence"][0]["snippet"]


def test_extract_evidence_snippet_limits_output_around_match() -> None:
    text = "Opening context. This sentence contains graph neural network evidence for the model. Closing context."

    snippet = extract_evidence_snippet(text, "graph neural network", max_chars=80)

    assert snippet == "This sentence contains graph neural network evidence for the model."


def test_selected_suggestion_values_require_explicit_selection() -> None:
    suggestions = explain_tag_book_suggestions(
        {
            "title": "Arabidopsis lateral root CRISPR screen",
            "abstract": "A genome-wide CRISPR screen was performed.",
            "tags": "",
        }
    )
    lateral = next(item for item in suggestions if item["canonical"] == "lateral-root")
    crispr = next(item for item in suggestions if item["canonical"] == "crispr-screen")

    assert selected_suggestion_tag_values(suggestions, []) == []
    assert selected_suggestion_tag_values(suggestions, [suggestion_selection_id(lateral)]) == ["lateral-root"]
    assert selected_suggestion_tag_values(suggestions, [suggestion_selection_id(crispr)]) == ["crispr-screen"]
    assert "crispr-screen" not in load_tag_book()["tags"]


def test_category_grouping() -> None:
    grouped = group_suggestions_by_category(
        [
            {"canonical": "synthetic-biology", "category": "field"},
            {"canonical": "single-cell-rna-seq", "category": "assay"},
        ]
    )

    assert list(grouped) == ["assay", "field"]
    assert grouped["field"][0]["canonical"] == "synthetic-biology"


def test_legacy_tag_config_paths_still_load() -> None:
    workspace = make_workspace("tag-book-legacy")
    rule_path = workspace / "tag_rules.json"
    registry_path = workspace / "canonical_tags.json"
    rule_path.write_text(
        json.dumps({"legacy-tag": {"category": "concept", "aliases": ["Legacy Tag"], "weight": 3}}),
        encoding="utf-8",
    )
    registry_path.write_text(
        json.dumps(
            {
                "legacy-tag": {
                    "label": "Legacy Tag",
                    "category": "concept",
                    "aliases": ["Legacy Tag"],
                    "status": "active",
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_tag_rules(rule_path)["legacy-tag"]["weight"] == 3
    assert load_canonical_tags(registry_path)["legacy-tag"]["label"] == "Legacy Tag"
