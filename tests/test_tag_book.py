import json

from ingest.tag_suggester import load_canonical_tags, load_tag_rules
from services.tag_book import (
    explain_tag_book_suggestions,
    group_suggestions_by_category,
    load_tag_book,
    normalize_tag,
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


def test_alias_normalization_is_kebab_case() -> None:
    assert normalize_tag(" Single Cell RNA Seq ") == "single-cell-rna-seq"
    assert normalize_tag("sc RNA-seq") == "sc-rna-seq"


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
    assert synthetic["matched_fields"] == ["abstract", "title"]


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
    suggestions = explain_tag_book_suggestions({"keywords": "scRNA-seq", "tags": ""})
    single_cell = next(item for item in suggestions if item["canonical"] == "single-cell-rna-seq")

    assert single_cell["display"] == "Single-cell RNA-seq"
    assert single_cell["source"] == "keywords"
    assert single_cell["matched_text"] == "scRNA-seq"
    assert single_cell["reason"]
    assert single_cell["evidence"][0]["source"] == "keywords"


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
