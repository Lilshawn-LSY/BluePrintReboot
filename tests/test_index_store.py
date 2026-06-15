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


def test_update_index_from_scan_appends_without_duplicates() -> None:
    workspace = make_workspace("index")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = data_dir / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    notes_dir.mkdir()
    (papers_dir / "Paper.pdf").write_bytes(b"%PDF-1.4\n")

    first = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    second = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(first) == 1
    assert len(second) == 1
    assert load_index(index_csv).iloc[0]["filename"] == "Paper.pdf"


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
    assert row["tags"] == ""
    assert row["status"] == "unread"
    assert row["reading_priority"] == "normal"
    assert row["metadata_source"] == ""
    assert row["metadata_confidence"] == ""
    assert row["metadata_checked_at"] == ""
    assert row["note_path"].endswith("paper-1.md")
    assert row["added_at"]
    assert row["updated_at"]


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
    assert row["metadata_source"] == "crossref"
    assert row["metadata_confidence"] == "high"
    assert row["metadata_checked_at"] == "2026-06-13T00:00:00+00:00"
    assert row["tags"] == "keep, tags"
    assert row["status"] == "reading"
    assert row["reading_priority"] == "high"
