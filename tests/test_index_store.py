import hashlib
import json
from pathlib import Path

import pandas as pd

from storage.index_store import (
    INDEX_COLUMNS,
    accept_crossref_metadata,
    load_index,
    save_index,
    update_index_from_scan,
    update_paper_metadata,
)
from tests.helpers import make_workspace


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakePdfReader:
    def __init__(self, text: str) -> None:
        self.pages = [FakePage(text)]


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def test_update_index_from_scan_appends_without_duplicates() -> None:
    workspace = make_workspace("index")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = data_dir / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    notes_dir.mkdir()
    contents = b"%PDF-1.4\n"
    (papers_dir / "Paper.pdf").write_bytes(contents)

    first = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    second = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(first) == 1
    assert len(second) == 1
    assert load_index(index_csv).iloc[0]["filename"] == "Paper.pdf"
    assert load_index(index_csv).iloc[0]["pdf_sha256"] == _sha256(contents)


def test_update_index_from_scan_auto_detects_and_normalizes_doi(monkeypatch) -> None:
    workspace = make_workspace("index-scan-doi")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = data_dir / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    notes_dir.mkdir()
    (papers_dir / "Detected.pdf").write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "ingest.document_text.PdfReader",
        lambda path: FakePdfReader("Article text doi: 10.1111/PCE.13021."),
    )

    updated = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)

    assert updated.iloc[0]["doi"] == "10.1111/pce.13021"
    assert updated.iloc[0]["doi_source"] == "pypdf"
    assert updated.iloc[0]["extraction_source"] == "pypdf"
    assert updated.iloc[0]["extraction_checked_at"]


def test_update_index_from_scan_does_not_overwrite_existing_doi(monkeypatch) -> None:
    workspace = make_workspace("index-scan-no-overwrite")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = data_dir / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    notes_dir.mkdir()
    (papers_dir / "Manual.pdf").write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "ingest.document_text.PdfReader",
        lambda path: FakePdfReader("Article text DOI 10.1111/first."),
    )

    first = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    paper_id = first.iloc[0]["paper_id"]
    update_paper_metadata(paper_id, {"doi": "10.2222/manual"}, index_csv=index_csv)
    monkeypatch.setattr(
        "ingest.document_text.PdfReader",
        lambda path: FakePdfReader("Article text DOI 10.3333/replacement."),
    )

    rescanned = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)

    assert rescanned.iloc[0]["doi"] == "10.2222/manual"
    assert rescanned.iloc[0]["doi_source"] == "manual"


def test_update_index_from_scan_survives_pdf_text_extraction_failure(monkeypatch) -> None:
    workspace = make_workspace("index-scan-doi-failure")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = data_dir / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    notes_dir.mkdir()
    (papers_dir / "Unreadable.pdf").write_bytes(b"%PDF-1.4\n")

    def fail_reader(path):
        raise ValueError("cannot read pdf text")

    monkeypatch.setattr("ingest.document_text.PdfReader", fail_reader)
    monkeypatch.setattr("ingest.document_text.MarkItDown", None)

    updated = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(updated) == 1
    assert updated.iloc[0]["doi"] == ""


def test_v1_index_is_migrated_to_v3_columns() -> None:
    workspace = make_workspace("migration")
    index_csv = workspace / "data" / "paper_index.csv"
    index_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "paper_id": "paper-1",
                "filename": "Old Paper.pdf",
                "filepath": "C:\\papers\\Old Paper.pdf",
                "title": "",
                "status": "",
                "note_path": "",
                "added_at": "",
                "updated_at": "",
                "custom_extra": "keep me",
            }
        ]
    ).to_csv(index_csv, index=False)

    migrated = load_index(index_csv)

    for column in INDEX_COLUMNS:
        assert column in migrated.columns
    row = migrated.iloc[0]
    assert row["title"] == "Old Paper"
    assert row["authors"] == ""
    assert row["journal"] == ""
    assert row["doi"] == ""
    assert row["pdf_sha256"] == ""
    assert row["abstract"] == ""
    assert row["keywords"] == ""
    assert row["tags"] == ""
    assert row["status"] == "unread"
    assert row["reading_priority"] == "normal"
    assert row["doi_source"] == ""
    assert row["extraction_source"] == ""
    assert row["extraction_checked_at"] == ""
    assert row["metadata_source"] == ""
    assert row["metadata_confidence"] == ""
    assert row["metadata_checked_at"] == ""
    assert row["note_path"].endswith("paper-1.md")
    assert row["added_at"]
    assert row["updated_at"]
    assert row["custom_extra"] == "keep me"


def test_legacy_index_backfills_pdf_sha256_when_pdf_exists() -> None:
    workspace = make_workspace("migration-pdf-sha256")
    papers_dir = workspace / "papers"
    index_csv = workspace / "data" / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    index_csv.parent.mkdir(parents=True)
    contents = b"%PDF-1.4\nlegacy hash"
    pdf_path = papers_dir / "Legacy.pdf"
    pdf_path.write_bytes(contents)
    pd.DataFrame(
        [
            {
                "paper_id": "legacy-paper-id",
                "filename": pdf_path.name,
                "filepath": str(pdf_path.resolve()),
                "title": "Legacy",
            }
        ]
    ).to_csv(index_csv, index=False)

    migrated = load_index(index_csv)

    assert migrated.iloc[0]["pdf_sha256"] == _sha256(contents)
    saved = pd.read_csv(index_csv, dtype=str).fillna("")
    assert "pdf_sha256" in saved.columns
    assert saved.iloc[0]["pdf_sha256"] == _sha256(contents)


def test_external_pdf_rename_preserves_paper_id_by_pdf_hash() -> None:
    workspace = make_workspace("hash-rename")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    note_blocks_dir = data_dir / "note_blocks"
    projects_dir = data_dir / "projects"
    index_csv = data_dir / "paper_index.csv"
    for directory in (papers_dir, notes_dir, note_blocks_dir, projects_dir):
        directory.mkdir(parents=True)
    contents = b"%PDF-1.4\nsame paper bytes"
    original = papers_dir / "Original.pdf"
    renamed = papers_dir / "Renamed.pdf"
    original.write_bytes(contents)

    first = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    paper_id = first.iloc[0]["paper_id"]
    note_path = Path(first.iloc[0]["note_path"])
    note_path.write_text("note sentinel", encoding="utf-8")
    (note_blocks_dir / f"{paper_id}.json").write_text("[]", encoding="utf-8")
    project_links_path = projects_dir / "project_links.json"
    project_links_path.write_text(
        json.dumps(
            [
                {
                    "id": "link-1",
                    "project_id": "project-1",
                    "paper_id": paper_id,
                    "target_type": "paper",
                    "target_id": paper_id,
                }
            ]
        ),
        encoding="utf-8",
    )

    original.rename(renamed)
    rescanned = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    row = rescanned.iloc[0]

    assert len(rescanned) == 1
    assert row["paper_id"] == paper_id
    assert row["filename"] == "Renamed.pdf"
    assert row["filepath"] == str(renamed.resolve())
    assert row["pdf_sha256"] == _sha256(contents)
    assert row["note_path"] == str(note_path)
    assert note_path.read_text(encoding="utf-8") == "note sentinel"
    assert (note_blocks_dir / f"{paper_id}.json").exists()
    assert paper_id in project_links_path.read_text(encoding="utf-8")


def test_same_hash_copy_is_left_unindexed_instead_of_creating_duplicate_row() -> None:
    workspace = make_workspace("hash-duplicate-copy")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = data_dir / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    notes_dir.mkdir()
    contents = b"%PDF-1.4\nsame content"
    original = papers_dir / "Original.pdf"
    copy = papers_dir / "Copy.pdf"
    original.write_bytes(contents)
    first = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    paper_id = first.iloc[0]["paper_id"]

    copy.write_bytes(contents)
    rescanned = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(rescanned) == 1
    assert rescanned.iloc[0]["paper_id"] == paper_id
    assert rescanned.iloc[0]["filename"] == "Original.pdf"
    assert str(copy.resolve()) not in set(rescanned["filepath"].tolist())


def test_rescan_preserves_manual_metadata() -> None:
    workspace = make_workspace("preserve")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = data_dir / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    notes_dir.mkdir()
    (papers_dir / "Manual.pdf").write_bytes(b"%PDF-1.4\n")

    first = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    paper_id = first.iloc[0]["paper_id"]
    update_paper_metadata(
        paper_id,
        {
            "title": "Manual Title",
            "authors": "Researcher A",
            "journal": "Local Journal",
            "doi": "10.1234/local",
            "tags": "manual, important",
            "reading_priority": "high",
        },
        index_csv=index_csv,
    )

    rescanned = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    row = rescanned.iloc[0]

    assert row["title"] == "Manual Title"
    assert row["authors"] == "Researcher A"
    assert row["journal"] == "Local Journal"
    assert row["doi"] == "10.1234/local"
    assert row["doi_source"] == "manual"
    assert row["tags"] == "manual, important"
    assert row["reading_priority"] == "high"


def test_update_paper_metadata_updates_only_target_row() -> None:
    workspace = make_workspace("metadata-update")
    index_csv = workspace / "data" / "paper_index.csv"
    rows = pd.DataFrame(
        [
            {
                "paper_id": "paper-1",
                "filename": "One.pdf",
                "filepath": "One.pdf",
                "title": "One",
                "authors": "",
                "journal": "",
                "doi": "",
                "tags": "",
                "reading_priority": "normal",
            },
            {
                "paper_id": "paper-2",
                "filename": "Two.pdf",
                "filepath": "Two.pdf",
                "title": "Two",
                "authors": "",
                "journal": "",
                "doi": "",
                "tags": "",
                "reading_priority": "normal",
            },
        ]
    )
    save_index(rows, index_csv)

    updated = update_paper_metadata(
        "paper-2",
        {"title": "Updated Two", "authors": "Author Two", "reading_priority": "high"},
        index_csv=index_csv,
    )

    row_one = updated[updated["paper_id"] == "paper-1"].iloc[0]
    row_two = updated[updated["paper_id"] == "paper-2"].iloc[0]
    assert row_one["title"] == "One"
    assert row_one["authors"] == ""
    assert row_two["title"] == "Updated Two"
    assert row_two["authors"] == "Author Two"
    assert row_two["reading_priority"] == "high"


def test_update_paper_metadata_normalizes_doi_before_saving() -> None:
    workspace = make_workspace("metadata-doi-normalize")
    index_csv = workspace / "data" / "paper_index.csv"
    save_index(
        pd.DataFrame(
            [
                {
                    "paper_id": "paper-1",
                    "filename": "One.pdf",
                    "filepath": "One.pdf",
                    "title": "One",
                    "doi": "",
                }
            ]
        ),
        index_csv,
    )

    updated = update_paper_metadata(
        "paper-1",
        {"doi": "doi: 10.1111/PCE.13021"},
        index_csv=index_csv,
    )

    assert updated.iloc[0]["doi"] == "10.1111/pce.13021"


def test_save_index_normalizes_existing_doi_values() -> None:
    workspace = make_workspace("save-doi-normalize")
    index_csv = workspace / "data" / "paper_index.csv"

    save_index(
        pd.DataFrame(
            [
                {
                    "paper_id": "paper-1",
                    "filename": "One.pdf",
                    "filepath": "One.pdf",
                    "title": "One",
                    "doi": "https://doi.org/10.1111/PCE.13021",
                }
            ]
        ),
        index_csv,
    )

    assert load_index(index_csv).iloc[0]["doi"] == "10.1111/pce.13021"


def test_accept_crossref_metadata_preserves_workflow_fields() -> None:
    workspace = make_workspace("crossref-accept")
    index_csv = workspace / "data" / "paper_index.csv"
    save_index(
        pd.DataFrame(
            [
                {
                    "paper_id": "paper-1",
                    "filename": "One.pdf",
                    "filepath": "One.pdf",
                    "title": "Manual Title",
                    "authors": "Manual Author",
                    "year": "",
                    "journal": "",
                    "doi": "10.1000/manual",
                    "tags": "keep, tags",
                    "status": "reading",
                    "reading_priority": "high",
                }
            ]
        ),
        index_csv,
    )

    updated = accept_crossref_metadata(
        "paper-1",
        {
            "title": "Crossref Title",
            "authors": "Crossref Author",
            "year": "2024",
            "journal": "Crossref Journal",
            "doi": "DOI 10.1000/Crossref",
            "metadata_source": "crossref",
            "metadata_confidence": "high",
            "metadata_checked_at": "2026-06-13T00:00:00+00:00",
            "tags": "should not apply",
            "status": "read",
            "reading_priority": "low",
        },
        index_csv=index_csv,
    )

    row = updated.iloc[0]
    assert row["title"] == "Crossref Title"
    assert row["authors"] == "Crossref Author"
    assert row["year"] == "2024"
    assert row["journal"] == "Crossref Journal"
    assert row["doi"] == "10.1000/crossref"
    assert row["doi_source"] == "crossref"
    assert row["metadata_source"] == "crossref"
    assert row["metadata_confidence"] == "high"
    assert row["metadata_checked_at"] == "2026-06-13T00:00:00+00:00"
    assert row["tags"] == "keep, tags"
    assert row["status"] == "reading"
    assert row["reading_priority"] == "high"


def test_accept_crossref_metadata_does_not_erase_existing_values_with_blanks() -> None:
    workspace = make_workspace("crossref-accept-non-empty-overlay")
    index_csv = workspace / "data" / "paper_index.csv"
    save_index(
        pd.DataFrame(
            [
                {
                    "paper_id": "paper-1",
                    "filename": "One.pdf",
                    "filepath": "One.pdf",
                    "title": "Manual Title",
                    "authors": "Manual Author",
                    "year": "2024",
                    "journal": "Manual Journal",
                    "abstract": "Manual abstract",
                    "keywords": "manual, keywords",
                    "doi": "10.1000/manual",
                }
            ]
        ),
        index_csv,
    )

    updated = accept_crossref_metadata(
        "paper-1",
        {
            "title": "Crossref Title",
            "authors": "",
            "year": "",
            "journal": "",
            "abstract": "",
            "keywords": "",
            "doi": "",
            "metadata_source": "crossref",
            "metadata_confidence": "partial",
        },
        index_csv=index_csv,
    )

    row = updated.iloc[0]
    assert row["title"] == "Crossref Title"
    assert row["authors"] == "Manual Author"
    assert row["year"] == "2024"
    assert row["journal"] == "Manual Journal"
    assert row["abstract"] == "Manual abstract"
    assert row["keywords"] == "manual, keywords"
    assert row["doi"] == "10.1000/manual"
    assert row["metadata_source"] == "crossref"
    assert row["metadata_confidence"] == "partial"
