from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest

from services.note_import import (
    DuplicateNoteImportError,
    apply_external_note_import,
    build_structured_block_candidates,
    extract_docx_paragraph_text,
    has_duplicate_note_import,
    load_note_import_log,
    match_note_import_to_papers,
    parse_external_note_file,
    parse_external_note_text,
)
from services.reading_note_template import (
    apply_reading_note_template_to_text,
    get_canonical_reading_note_template,
    reading_note_template_file_text,
    refresh_reading_note_header,
    render_reading_note_template,
)
from storage.atomic_json import CorruptJsonError
from storage.index_store import save_index
from storage.note_block_store import list_note_blocks
from storage.note_store import load_note_text, save_note_text
from tests.helpers import make_workspace


SAMPLE_TEMPLATE = """# BluePrint Reading Note

template_version: 1.0
paper_id: paper-1
title: Attention Is All You Need
doi: 10.48550/arXiv.1706.03762
arxiv_id: 1706.03762v7
year: 2017
first_author: Vaswani
tags: transformer, attention

## One-line Summary

Transformers replace recurrence with attention.

## Summary

The paper introduces the Transformer architecture.

## Key Claims

* Attention is enough for sequence transduction.
* Parallel training improves efficiency.

## Methods

* Multi-head self-attention.

## Evidence / Results

* Better BLEU on translation benchmarks.

## Questions

*

## Ideas

* Try attention for long biological sequences.

## Limitations

*

## Raw Notes

Printed margin notes go here.
"""


def _docx_bytes(paragraphs: list[str]) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>" for paragraph in paragraphs)
        + "</w:body></w:document>"
    )
    target = BytesIO()
    with ZipFile(target, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return target.getvalue()


def test_markdown_template_parsing_extracts_header_fields_and_sections() -> None:
    parsed = parse_external_note_text(SAMPLE_TEMPLATE, source_filename="note.md")

    assert parsed["template_version"] == "1.0"
    assert parsed["header_fields"]["paper_id"] == "paper-1"
    assert parsed["header_fields"]["title"] == "Attention Is All You Need"
    assert parsed["header_fields"]["tags"] == "transformer, attention"
    assert parsed["sections"]["One-line Summary"] == "Transformers replace recurrence with attention."
    assert parsed["sections"]["Raw Notes"] == "Printed margin notes go here."
    assert parsed["parse_errors"] == []


def test_canonical_template_generation_without_paper_record() -> None:
    template = get_canonical_reading_note_template()

    assert template.startswith("# BluePrint Reading Note")
    assert "template_version: 1.0" in template
    for section in (
        "## One-line Summary",
        "## Summary",
        "## Key Claims",
        "## Methods",
        "## Evidence / Results",
        "## Questions",
        "## Ideas",
        "## Limitations",
        "## Raw Notes",
    ):
        assert section in template


def test_canonical_template_generation_with_paper_record() -> None:
    template = render_reading_note_template(
        {
            "paper_id": "paper-1",
            "title": "Paper Title",
            "doi": "10.48550/arXiv.1706.03762",
            "filename": "1706.03762v2.pdf",
            "year": "2017",
            "authors": "Ada Lovelace; Grace Hopper",
            "tags": "attention, transformer",
        }
    )

    assert "paper_id: paper-1" in template
    assert "title: Paper Title" in template
    assert "doi: 10.48550/arXiv.1706.03762" in template
    assert "arxiv_id: 1706.03762" in template
    assert "first_author: Ada Lovelace" in template
    assert "tags: attention, transformer" in template


def test_generated_template_can_be_parsed_by_import_parser() -> None:
    template = render_reading_note_template({"paper_id": "paper-1", "title": "Paper Title"})

    parsed = parse_external_note_text(template, source_filename="template.md")

    assert parsed["parse_errors"] == []
    assert parsed["header_fields"]["paper_id"] == "paper-1"
    assert set(parsed["sections"]) >= {"One-line Summary", "Raw Notes"}


def test_downloadable_template_uses_same_section_contract() -> None:
    file_text = reading_note_template_file_text()
    helper_text = get_canonical_reading_note_template()

    assert file_text == helper_text


def test_parser_accepts_previous_external_template_title() -> None:
    legacy = SAMPLE_TEMPLATE.replace("# BluePrint Reading Note", "# BluePrint External Reading Note", 1)

    parsed = parse_external_note_text(legacy, source_filename="legacy.md")

    assert parsed["parse_errors"] == []
    assert parsed["header_fields"]["paper_id"] == "paper-1"


def test_template_insertion_does_not_overwrite_existing_non_empty_note() -> None:
    result = apply_reading_note_template_to_text("existing note", {"paper_id": "paper-1"})

    assert result["changed"] is False
    assert result["text"] == "existing note"
    appended = apply_reading_note_template_to_text("existing note", {"paper_id": "paper-1"}, append_if_non_empty=True)
    assert appended["changed"] is True
    assert str(appended["text"]).startswith("existing note\n\n# BluePrint Reading Note")


def test_header_refresh_updates_metadata_without_changing_body_sections() -> None:
    updated_record = {
        "paper_id": "paper-1",
        "title": "Updated Transformer Paper",
        "doi": "10.1000/updated",
        "year": "2024",
        "authors": "Grace Hopper; Ada Lovelace",
        "tags": "updated, transformer",
    }

    result = refresh_reading_note_header(SAMPLE_TEMPLATE, updated_record)

    refreshed = str(result["text"])
    assert result["changed"] is True
    assert "title: Updated Transformer Paper" in refreshed
    assert "doi: 10.1000/updated" in refreshed
    assert "year: 2024" in refreshed
    assert "first_author: Grace Hopper" in refreshed
    assert "tags: updated, transformer" in refreshed
    assert refreshed.split("## One-line Summary", 1)[1] == SAMPLE_TEMPLATE.split("## One-line Summary", 1)[1]


def test_header_refresh_ignores_freeform_notes() -> None:
    freeform = "Personal reading notes\n\n## Summary\n\nDo not rewrite me.\n"

    result = refresh_reading_note_header(freeform, {"paper_id": "paper-1", "title": "Updated"})

    assert result["changed"] is False
    assert result["text"] == freeform


def test_bullet_sections_convert_into_multiple_block_candidates_and_ignore_empty_sections() -> None:
    parsed = parse_external_note_text(SAMPLE_TEMPLATE, source_filename="note.md")

    candidates = build_structured_block_candidates(parsed)

    assert [candidate["block_type"] for candidate in candidates] == [
        "summary",
        "summary",
        "claim",
        "claim",
        "method",
        "evidence",
        "idea",
    ]
    assert candidates[2]["text"] == "Attention is enough for sequence transduction."
    assert not any(candidate["block_type"] == "question" for candidate in candidates)
    assert not any(candidate["block_type"] == "limitation" for candidate in candidates)


def test_docx_paragraph_extraction_and_parse() -> None:
    content = _docx_bytes(SAMPLE_TEMPLATE.splitlines())

    text, diagnostics, parse_errors = extract_docx_paragraph_text(content)
    parsed = parse_external_note_file("note.docx", content)

    assert "BluePrint Reading Note" in text
    assert diagnostics == ["Read 28 DOCX paragraphs."]
    assert parse_errors == []
    assert parsed["header_fields"]["paper_id"] == "paper-1"
    assert parsed["sections"]["Summary"] == "The paper introduces the Transformer architecture."


def test_malformed_template_returns_parse_errors_without_crashing() -> None:
    parsed = parse_external_note_text("not the template\njust some text", source_filename="bad.md")

    assert "No recognized template sections were found." in parsed["parse_errors"]
    assert any("Template title was not found" in diagnostic for diagnostic in parsed["diagnostics"])


def test_paper_id_exact_matching() -> None:
    parsed = parse_external_note_text(SAMPLE_TEMPLATE, source_filename="note.md")
    index = pd.DataFrame([{"paper_id": "paper-1", "title": "Different", "doi": ""}])

    match = match_note_import_to_papers(parsed, index)

    assert match["auto_target_paper_id"] == "paper-1"
    assert match["confident_matches"][0]["match_type"] == "paper_id"


def test_doi_exact_matching_when_paper_id_missing() -> None:
    parsed = parse_external_note_text(SAMPLE_TEMPLATE.replace("paper_id: paper-1", "paper_id:"), source_filename="note.md")
    index = pd.DataFrame([{"paper_id": "paper-2", "title": "Different", "doi": "DOI:10.48550/ARXIV.1706.03762"}])

    match = match_note_import_to_papers(parsed, index)

    assert match["auto_target_paper_id"] == "paper-2"
    assert match["confident_matches"][0]["match_type"] == "doi"


def test_ambiguous_title_matching_does_not_auto_apply() -> None:
    parsed = parse_external_note_text(
        SAMPLE_TEMPLATE.replace("paper_id: paper-1", "paper_id:").replace("doi: 10.48550/arXiv.1706.03762", "doi:"),
        source_filename="note.md",
    )
    index = pd.DataFrame(
        [
            {"paper_id": "paper-1", "title": "Attention Is All You Need", "doi": ""},
            {"paper_id": "paper-2", "title": "Attention Is All You Need", "doi": ""},
        ]
    )

    match = match_note_import_to_papers(parsed, index)

    assert match["auto_target_paper_id"] == ""
    assert [candidate["paper_id"] for candidate in match["title_candidates"]] == ["paper-1", "paper-2"]


def test_duplicate_import_detection() -> None:
    workspace = make_workspace("note-import-duplicate")
    log_path = workspace / "data" / "note_imports.json"
    parsed = parse_external_note_text(SAMPLE_TEMPLATE, source_filename="note.md")
    record = {"paper_id": "paper-1", "title": "Paper", "filename": "Paper.pdf"}

    apply_external_note_import(
        record,
        parsed,
        notes_dir=workspace / "notes",
        note_blocks_dir=workspace / "data" / "note_blocks",
        log_path=log_path,
    )

    assert has_duplicate_note_import("paper-1", parsed["source_sha256"], log_path=log_path) is True
    assert has_duplicate_note_import("paper-2", parsed["source_sha256"], log_path=log_path) is False


def test_corrupt_note_import_log_raises_typed_error_and_preserves_file() -> None:
    workspace = make_workspace("note-import-corrupt-log")
    log_path = workspace / "data" / "note_imports.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("{not valid json", encoding="utf-8")
    before = log_path.read_text(encoding="utf-8")

    with pytest.raises(CorruptJsonError) as error:
        load_note_import_log(log_path)

    assert error.value.path == log_path
    assert "Note import log is invalid JSON" in error.value.summary
    assert log_path.read_text(encoding="utf-8") == before


def test_duplicate_import_is_blocked_by_default() -> None:
    workspace = make_workspace("note-import-duplicate-block")
    notes_dir = workspace / "notes"
    note_blocks_dir = workspace / "data" / "note_blocks"
    log_path = workspace / "data" / "note_imports.json"
    record = {"paper_id": "paper-1", "title": "Paper", "filename": "Paper.pdf"}
    parsed = parse_external_note_text(SAMPLE_TEMPLATE, source_filename="note.md")

    apply_external_note_import(
        record,
        parsed,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        log_path=log_path,
    )
    note_text_after_first_import = load_note_text(record, notes_dir=notes_dir)

    with pytest.raises(DuplicateNoteImportError):
        apply_external_note_import(
            record,
            parsed,
            notes_dir=notes_dir,
            note_blocks_dir=note_blocks_dir,
            log_path=log_path,
        )

    assert len(load_note_import_log(log_path)) == 1
    assert len(list_note_blocks("paper-1", note_blocks_dir)) == 7
    assert load_note_text(record, notes_dir=notes_dir) == note_text_after_first_import


def test_force_reimport_allows_deliberate_duplicate_import() -> None:
    workspace = make_workspace("note-import-duplicate-force")
    notes_dir = workspace / "notes"
    note_blocks_dir = workspace / "data" / "note_blocks"
    log_path = workspace / "data" / "note_imports.json"
    record = {"paper_id": "paper-1", "title": "Paper", "filename": "Paper.pdf"}
    parsed = parse_external_note_text(SAMPLE_TEMPLATE, source_filename="note.md")

    first = apply_external_note_import(
        record,
        parsed,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        log_path=log_path,
    )
    second = apply_external_note_import(
        record,
        parsed,
        force_reimport=True,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        log_path=log_path,
    )

    log_entries = load_note_import_log(log_path)
    assert len(log_entries) == 2
    assert first["import_id"] != second["import_id"]
    assert len(list_note_blocks("paper-1", note_blocks_dir)) == 14


def test_import_apply_appends_markdown_without_overwriting_existing_note() -> None:
    workspace = make_workspace("note-import-markdown")
    notes_dir = workspace / "notes"
    note_blocks_dir = workspace / "data" / "note_blocks"
    log_path = workspace / "data" / "note_imports.json"
    record = {"paper_id": "paper-1", "title": "Paper", "filename": "Paper.pdf"}
    save_note_text(record, "existing note", notes_dir=notes_dir)
    parsed = parse_external_note_text(SAMPLE_TEMPLATE, source_filename="note.md")

    result = apply_external_note_import(
        record,
        parsed,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        log_path=log_path,
    )

    text = load_note_text(record, notes_dir=notes_dir)
    assert text.startswith("existing note")
    assert "## BluePrint Reading Note Import -" in text
    assert "Printed margin notes go here." in text
    assert result["appended_markdown"] is True


def test_import_apply_creates_structured_note_blocks_and_log_entry() -> None:
    workspace = make_workspace("note-import-blocks")
    record = {"paper_id": "paper-1", "title": "Paper", "filename": "Paper.pdf"}
    parsed = parse_external_note_text(SAMPLE_TEMPLATE, source_filename="note.md")

    result = apply_external_note_import(
        record,
        parsed,
        notes_dir=workspace / "notes",
        note_blocks_dir=workspace / "data" / "note_blocks",
        log_path=workspace / "data" / "note_imports.json",
    )

    blocks = list_note_blocks("paper-1", workspace / "data" / "note_blocks")
    log_entries = load_note_import_log(workspace / "data" / "note_imports.json")
    assert len(blocks) == 7
    assert [block["id"] for block in blocks] == result["created_block_ids"]
    assert blocks[0]["block_type"] == "summary"
    assert blocks[2]["block_type"] == "claim"
    assert log_entries[0]["target_paper_id"] == "paper-1"
    assert log_entries[0]["created_block_ids"] == result["created_block_ids"]
