from ingest.tag_suggester import (
    audit_library_tags,
    build_tag_suggestion_record,
    explain_tag_suggestions,
    load_tag_rules,
    merge_tags,
    normalize_tag,
    parse_tags,
    suggest_tags,
    validate_tag_rules,
)


def test_load_tag_rules_from_config() -> None:
    rules = load_tag_rules()

    assert "synthetic-biology" in rules
    assert rules["synthetic-biology"]["category"] == "field"
    assert "synthetic biology" in rules["synthetic-biology"]["aliases"]
    assert isinstance(rules["synthetic-biology"]["weight"], int)


def test_valid_rulebook_has_no_validation_warnings() -> None:
    assert validate_tag_rules(load_tag_rules()) == []


def test_build_tag_suggestion_record_overlays_form_values() -> None:
    record = {
        "title": "Saved Title",
        "abstract": "Saved abstract",
        "keywords": "",
        "journal": "Saved Journal",
        "filename": "saved.pdf",
        "tags": "saved-tag",
    }
    form_values = {
        "title": "Unsaved Title",
        "abstract": "Unsaved abstract",
        "keywords": "scRNA-seq",
        "journal": "Unsaved Journal",
        "filename": "form.pdf",
        "tags": "form-tag",
    }

    built = build_tag_suggestion_record(record, form_values=form_values)

    assert built["title"] == "Unsaved Title"
    assert built["abstract"] == "Unsaved abstract"
    assert built["keywords"] == "scRNA-seq"
    assert built["journal"] == "Unsaved Journal"
    assert built["filename"] == "form.pdf"
    assert built["tags"] == "form-tag"


def test_build_tag_suggestion_record_uses_crossref_preview_fields() -> None:
    built = build_tag_suggestion_record(
        {"title": "Saved", "abstract": "Saved abstract", "keywords": "", "journal": ""},
        form_values={"title": "Form title", "abstract": "Form abstract"},
        crossref_preview={
            "title": "Preview title",
            "abstract": "Preview abstract with metabolic engineering",
            "keywords": "single-cell RNA sequencing",
            "journal": "Preview Journal",
            "crossref_subjects": "Spatial Transcriptomics",
        },
    )

    assert built["title"] == "Preview title"
    assert built["abstract"] == "Preview abstract with metabolic engineering"
    assert built["keywords"] == "single-cell RNA sequencing"
    assert built["journal"] == "Preview Journal"
    assert built["crossref_subjects"] == "Spatial Transcriptomics"


def test_build_tag_suggestion_record_empty_preview_fields_do_not_erase_values() -> None:
    built = build_tag_suggestion_record(
        {"title": "Saved title", "abstract": "Saved abstract", "tags": "saved-tag"},
        form_values={"title": "Form title", "abstract": "Form abstract", "tags": "form-tag"},
        crossref_preview={"title": "", "abstract": "   ", "keywords": ""},
    )

    assert built["title"] == "Form title"
    assert built["abstract"] == "Form abstract"
    assert built["tags"] == "form-tag"


def test_validate_tag_rules_reports_duplicate_aliases() -> None:
    warnings = validate_tag_rules(
        {
            "first-tag": {"category": "test", "aliases": ["shared alias"], "weight": 1},
            "second-tag": {"category": "test", "aliases": ["shared-alias"], "weight": 1},
        }
    )

    assert any("used by both" in warning for warning in warnings)


def test_validate_tag_rules_reports_missing_required_fields_and_empty_aliases() -> None:
    warnings = validate_tag_rules(
        {
            "Bad Tag": {"aliases": [""], "weight": "heavy"},
            "missing-aliases": {"category": "test", "weight": 1},
            "missing-weight": {"category": "test", "aliases": ["ok"]},
        }
    )

    assert "Tag 'Bad Tag' is not normalized kebab-case." in warnings
    assert "Tag 'Bad Tag' is missing category." in warnings
    assert "Tag 'Bad Tag' weight must be numeric." in warnings
    assert "Tag 'Bad Tag' has an empty alias." in warnings
    assert "Tag 'missing-aliases' is missing aliases." in warnings
    assert "Tag 'missing-weight' is missing weight." in warnings


def test_normalize_tag() -> None:
    assert normalize_tag(" Single Cell RNA Seq ") == "single-cell-rna-seq"
    assert normalize_tag("AI/Biology") == "ai-biology"


def test_parse_tags_normalizes_and_deduplicates() -> None:
    assert parse_tags("Root Development; root-development, AI Biology") == [
        "root-development",
        "ai-biology",
    ]


def test_merge_tags_preserves_existing_tags_and_adds_unique_suggestions() -> None:
    merged = merge_tags("Existing Tag, root-development", ["root-development", "AI Biology"])

    assert merged == "existing-tag, root-development, ai-biology"


def test_audit_library_tags_reports_unknown_tags() -> None:
    audit = audit_library_tags(
        [{"tags": "synthetic-biology, custom-tag"}],
        {"synthetic-biology": {"category": "field", "aliases": ["synthetic biology"], "weight": 1}},
    )

    assert audit["known_tags"] == ["synthetic-biology"]
    assert audit["unknown_tags"] == ["custom-tag"]


def test_audit_library_tags_reports_unused_rulebook_tags_and_duplicates() -> None:
    audit = audit_library_tags(
        [{"tags": "Known Tag, known-tag"}],
        {
            "known-tag": {"category": "test", "aliases": ["known"], "weight": 1},
            "unused-tag": {"category": "test", "aliases": ["unused"], "weight": 1},
        },
    )

    assert audit["duplicate_normalized_tags"] == ["known-tag"]
    assert audit["unused_rulebook_tags"] == ["unused-tag"]


def test_suggest_tags_avoids_existing_tags_and_supports_future_fields() -> None:
    record = {
        "title": "Synthetic Biology review of root single-cell methods",
        "abstract": "Machine learning pipeline for Arabidopsis spatial transcriptomics.",
        "journal": "Bioinformatics",
        "filename": "protein design protocol.pdf",
        "tags": "Synthetic Biology, existing-tag",
        "semantic_scholar_fields": "ignored for now",
    }

    suggestions = suggest_tags(record)

    assert "synthetic-biology" not in suggestions
    assert "single-cell-rna-seq" in suggestions
    assert "pipeline" in suggestions
    assert "protocol" in suggestions


def test_suggest_tags_matches_scrna_seq_spelling() -> None:
    suggestions = suggest_tags({"keywords": "scRNA-seq analysis of root apical meristem"})

    assert "single-cell-rna-seq" in suggestions


def test_suggest_tags_uses_crossref_preview_abstract_and_keywords_before_accept() -> None:
    suggestion_record = build_tag_suggestion_record(
        {"title": "Saved paper", "tags": ""},
        crossref_preview={
            "abstract": "This study uses single-cell RNA sequencing and artificial intelligence.",
            "keywords": "spatial transcriptomics",
            "journal": "Plant Methods",
        },
    )

    suggestions = suggest_tags(suggestion_record)

    assert "single-cell-rna-seq" in suggestions
    assert "ai-biology" in suggestions
    assert "spatial-transcriptomics" in suggestions


def test_existing_tags_suppress_duplicate_suggestions_from_form_and_preview() -> None:
    suggestion_record = build_tag_suggestion_record(
        {"title": "", "tags": "single-cell-rna-seq"},
        form_values={"keywords": "scRNA-seq"},
        crossref_preview={"abstract": "single-cell RNA sequencing"},
    )

    assert "single-cell-rna-seq" not in suggest_tags(suggestion_record)


def test_source_aware_scoring_is_deterministic() -> None:
    rules = {
        "alpha-tag": {"category": "test", "aliases": ["shared"], "weight": 2},
        "beta-tag": {"category": "test", "aliases": ["shared"], "weight": 2},
        "high-score": {"category": "test", "aliases": ["priority"], "weight": 3},
    }
    record = {
        "title": "shared",
        "keywords": "priority",
    }

    explanations = explain_tag_suggestions(record, rules)

    assert [item["tag"] for item in explanations] == ["high-score", "alpha-tag", "beta-tag"]
    assert explanations[0]["score"] == 18
    assert explanations[1]["score"] == 8


def test_markdown_text_can_generate_suggestions() -> None:
    record = {
        "markdown_text": "This note discusses root apical meristem organization.",
        "tags": "",
    }

    assert "root-apical-meristem" in suggest_tags(record)


def test_crossref_subjects_can_generate_suggestions() -> None:
    record = {
        "crossref_subjects": "Metabolic Engineering; Spatial Transcriptomics",
        "tags": "",
    }

    suggestions = suggest_tags(record)

    assert "metabolic-engineering" in suggestions
    assert "spatial-transcriptomics" in suggestions


def test_absent_future_fields_do_not_break_behavior() -> None:
    assert suggest_tags({"title": "Arabidopsis root development protocol"})[:3] == [
        "arabidopsis",
        "root-development",
        "protocol",
    ]


def test_explain_tag_suggestions_returns_metadata() -> None:
    explanations = explain_tag_suggestions(
        {
            "title": "Bioinformatics method",
            "keywords": "Bioinformatics",
        }
    )
    bioinformatics = next(item for item in explanations if item["tag"] == "bioinformatics")

    assert bioinformatics["category"] == "method"
    assert bioinformatics["score"] == 70
    assert bioinformatics["matched_fields"] == ["keywords", "title"]
