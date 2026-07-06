from services.paper_text_profile_builder import build_paper_text_profile
from ingest.tag_suggester import build_tag_suggestion_record, explain_tag_suggestions
from storage.extracted_text_store import save_extracted_text
from storage.note_block_store import save_note_blocks
from tests.helpers import make_workspace


def test_profile_construction_from_index_metadata() -> None:
    workspace = make_workspace("paper-profile-builder-metadata")
    record = {
        "paper_id": "paper-1",
        "title": "Synthetic biology design in Arabidopsis",
        "abstract": "A deterministic profile should preserve metadata abstracts.",
        "keywords": "synthetic biology; Arabidopsis, root development",
        "filename": "fallback-title.pdf",
    }

    profile = build_paper_text_profile(
        record,
        notes_dir=workspace / "notes",
        note_blocks_dir=workspace / "note_blocks",
        extracted_text_dir=workspace / "extracted_text",
    )

    assert profile.schema_version == "1.0.15"
    assert profile.paper_id == "paper-1"
    assert profile.title == "Synthetic biology design in Arabidopsis"
    assert profile.abstract == "A deterministic profile should preserve metadata abstracts."
    assert profile.keywords == ["synthetic biology", "Arabidopsis", "root development"]
    assert profile.sources["title"] == "paper_index"
    assert profile.sources["abstract"] == "paper_index"
    assert profile.confidence["title"] == "high"
    assert profile.confidence["abstract"] == "high"
    assert profile.confidence["keywords"] == "high"
    assert profile.confidence["note_sections"] == "none"
    assert profile.generated_at


def test_profile_collects_reading_note_sections_and_note_blocks() -> None:
    workspace = make_workspace("paper-profile-builder-notes")
    notes_dir = workspace / "notes"
    note_blocks_dir = workspace / "note_blocks"
    notes_dir.mkdir(parents=True)
    (notes_dir / "paper-1.md").write_text(
        "\n".join(
            [
                "# BluePrint Reading Note",
                "",
                "template_version: 1.0",
                "paper_id: paper-1",
                "title: Test paper",
                "",
                "## Summary",
                "",
                "The summary discusses root development.",
                "",
                "## Methods",
                "",
                "* The note method uses microscopy.",
            ]
        ),
        encoding="utf-8",
    )
    save_note_blocks(
        "paper-1",
        [
            {
                "id": "block-1",
                "paper_id": "paper-1",
                "block_type": "evidence",
                "title": "Spatial evidence",
                "text": "Spatial transcriptomics evidence supports the claim.",
                "page": "",
                "figure": "",
                "quote": "",
                "tags": [],
            }
        ],
        note_blocks_dir,
    )

    profile = build_paper_text_profile(
        {"paper_id": "paper-1", "title": "Test paper"},
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        extracted_text_dir=workspace / "extracted_text",
    )

    assert "root development" in profile.note_sections["Summary"]
    assert "microscopy" in profile.note_sections["Methods"]
    assert "Spatial transcriptomics evidence" in profile.note_sections["Evidence / Results"]
    assert profile.sources["note_sections.Summary"] == "reading_note"
    assert profile.sources["note_sections.Evidence / Results"] == "note_blocks"
    assert profile.confidence["note_sections"] == "high"


def test_extracted_text_cache_is_only_abstract_fallback() -> None:
    workspace = make_workspace("paper-profile-builder-cache")
    extracted_text_dir = workspace / "extracted_text"
    save_extracted_text(
        "paper-1",
        "\n".join(
            [
                "Abstract",
                "This fallback abstract is long enough to be used, but remains low confidence.",
                "",
                "Methods",
                "A CRISPR screen appears here but should not become a profile note section.",
            ]
        ),
        extracted_text_dir,
    )

    profile = build_paper_text_profile(
        {"paper_id": "paper-1", "title": "Cache fallback paper"},
        notes_dir=workspace / "notes",
        note_blocks_dir=workspace / "note_blocks",
        extracted_text_dir=extracted_text_dir,
    )

    assert profile.abstract.startswith("This fallback abstract is long enough")
    assert profile.sources["abstract"] == "pdf_profile"
    assert profile.confidence["abstract"] == "medium"
    assert profile.note_sections == {}


def test_pdf_keywords_become_explicit_tag_suggestion_source() -> None:
    workspace = make_workspace("paper-profile-pdf-keywords")
    extracted_text_dir = workspace / "extracted_text"
    save_extracted_text(
        "paper-1",
        "\n".join(
            [
                "Generic Review",
                "Abstract",
                "This review summarizes plant development.",
                "Keywords",
                "lateral root; Arabidopsis",
            ]
        ),
        extracted_text_dir,
    )

    profile = build_paper_text_profile(
        {"paper_id": "paper-1", "title": "Generic Review", "keywords": "", "tags": ""},
        notes_dir=workspace / "notes",
        note_blocks_dir=workspace / "note_blocks",
        extracted_text_dir=extracted_text_dir,
    )
    suggestion_record = build_tag_suggestion_record(
        {"paper_id": "paper-1", "title": "Generic Review", "tags": ""},
        paper_text_profile=profile,
    )
    suggestions = explain_tag_suggestions(suggestion_record)
    lateral = next(item for item in suggestions if item["canonical"] == "lateral-root")

    assert profile.keywords == ["lateral root", "Arabidopsis"]
    assert suggestion_record["pdf_keywords"] == ["lateral root", "Arabidopsis"]
    assert lateral["matched_fields"] == ["pdf_keywords"]
    assert lateral["source_label"] == "pdf keywords"
