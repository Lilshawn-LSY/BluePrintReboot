import pandas as pd

from storage.index_store import filter_archived, load_index, set_paper_archived, update_index_from_scan, update_paper_metadata
from tests.helpers import make_workspace


def test_archive_migration_filter_and_round_trip_preserve_fields() -> None:
    root = make_workspace("archive-roundtrip")
    index = root / "data" / "paper_index.csv"
    index.parent.mkdir()
    pdf = root / "papers" / "paper.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"pdf")
    original = {"paper_id": "p1", "filename": pdf.name, "filepath": str(pdf.resolve()), "title": "Title", "status": "reading", "reading_priority": "high", "note_path": str((root / "notes" / "p1.md").resolve())}
    pd.DataFrame([original]).to_csv(index, index=False)

    migrated = load_index(index, papers_dir=pdf.parent)
    assert migrated.iloc[0]["is_archived"] == "false"
    before = migrated.iloc[0].to_dict()
    archived = set_paper_archived("p1", True, index)
    assert archived.iloc[0]["is_archived"] == "true"
    assert archived.iloc[0]["archived_at"]
    assert filter_archived(archived).empty
    assert len(filter_archived(archived, include_archived=True)) == 1
    assert len(filter_archived(archived, archived_only=True)) == 1
    for field in ("paper_id", "filepath", "note_path", "status", "reading_priority"):
        assert archived.iloc[0][field] == before[field]
    restored = set_paper_archived("p1", False, index)
    assert restored.iloc[0]["is_archived"] == "false"
    assert restored.iloc[0]["archived_at"] == ""


def test_scan_and_metadata_update_preserve_archive_fields() -> None:
    root = make_workspace("archive-scan")
    papers = root / "papers"
    notes = root / "notes"
    papers.mkdir(); notes.mkdir()
    (papers / "paper.pdf").write_bytes(b"pdf")
    index = root / "data" / "paper_index.csv"
    first = update_index_from_scan(index, papers, notes)
    paper_id = first.iloc[0]["paper_id"]
    set_paper_archived(paper_id, True, index)
    update_paper_metadata(paper_id, {"title": "Updated"}, index)
    rescanned = update_index_from_scan(index, papers, notes)
    assert rescanned.iloc[0]["is_archived"] == "true"
    assert rescanned.iloc[0]["archived_at"]
    assert rescanned.iloc[0]["title"] == "Updated"
