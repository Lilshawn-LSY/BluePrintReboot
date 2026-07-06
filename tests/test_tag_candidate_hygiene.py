from core.paper_text_profile import PaperTextProfile
from ingest.tag_suggester import explain_tag_suggestions
from services.tag_book import (
    clean_candidate_phrase,
    explain_tag_book_suggestions,
    load_tag_book,
    score_candidate_quality,
    selected_suggestion_tag_values,
    suggestion_selection_id,
)


def test_candidate_cleanup_strips_section_prefix_and_leading_article() -> None:
    cleaned = clean_candidate_phrase("Abstract A foundation model")

    assert cleaned["cleaned"] == "foundation model"
    assert cleaned["canonical"] == "foundation-model"
    assert any("abstract" in note for note in cleaned["cleanup_notes"])


def test_candidate_cleanup_removes_boilerplate_analysis_tail() -> None:
    cleaned = clean_candidate_phrase("gene/feature levels for the analysis")
    quality = score_candidate_quality("gene/feature levels for the analysis")

    assert cleaned["cleaned"] == "gene/feature"
    assert quality["quality"] == "rejected"
    assert quality["quality_reason"] == "too short or low information"


def test_candidate_quality_scores_high_medium_weak_and_rejected() -> None:
    high = score_candidate_quality(
        "spatial transcriptomics pipeline",
        [{"source": "keywords"}],
        category="method",
    )
    medium = score_candidate_quality(
        "image analysis",
        [{"source": "title"}],
        category="method",
    )
    weak = score_candidate_quality(
        "sample classification",
        [{"source": "abstract"}],
    )
    rejected = score_candidate_quality("a large-scale deep learning model", [{"source": "abstract"}])

    assert high["quality"] == "high"
    assert medium["quality"] == "medium"
    assert weak["quality"] == "weak"
    assert rejected["quality"] == "rejected"
    assert rejected["cleaned"] == "large-scale deep learning model"
    assert rejected["quality_reason"] == "generic model phrase"


def test_candidate_duplicate_alias_is_rejected_against_tag_book() -> None:
    quality = score_candidate_quality(
        "single-cell RNA sequencing",
        [{"source": "keywords"}],
        category="assay",
        tag_book=load_tag_book(),
    )

    assert quality["quality"] == "rejected"
    assert quality["duplicate_of_canonical"] == "single-cell-rna-seq"
    assert "already covered" in quality["quality_reason"]


def test_bad_candidate_examples_are_rejected_and_not_selectable() -> None:
    suggestions = explain_tag_book_suggestions(
        {
            "abstract": (
                "Abstract A foundation model improves embeddings. "
                "The data include gene/feature levels for the analysis. "
                "We avoid a large-scale deep learning model."
            ),
            "tags": "",
        }
    )
    rejected = [item for item in suggestions if item.get("kind") == "rejected_candidate"]
    rejected_by_display = {item["display"]: item for item in rejected}

    assert "foundation model" in rejected_by_display
    assert "gene/feature" in rejected_by_display
    assert "large-scale deep learning model" in rejected_by_display
    assert all(item["selectable"] is False for item in rejected)
    selected_ids = [suggestion_selection_id(item) for item in rejected]
    assert selected_suggestion_tag_values(suggestions, selected_ids) == []


def test_known_canonical_alias_matching_still_wins() -> None:
    suggestions = explain_tag_book_suggestions(
        {"title": "Single-cell RNA sequencing atlas", "tags": ""}
    )

    single_cell = next(item for item in suggestions if item["canonical"] == "single-cell-rna-seq")
    assert single_cell["kind"] == "known_canonical"
    assert single_cell["matched_fields"] == ["title"]


def test_paper_text_profile_note_methods_evidence_remains_usable() -> None:
    profile = PaperTextProfile(
        paper_id="paper-1",
        note_sections={"Methods": "We used ATAC-seq and flow cytometry in validation."},
    )

    suggestions = explain_tag_suggestions({"paper_id": "paper-1", "tags": ""}, paper_text_profile=profile)
    atac = next(item for item in suggestions if item["canonical"] == "atac-seq")

    assert atac["kind"] == "new_candidate"
    assert atac["matched_fields"] == ["note_methods"]
    assert atac["source_label"] == "note section: Methods"
    assert atac["quality"] in {"high", "medium"}
