from ingest.scanner import scan_papers
from tests.helpers import make_workspace


def test_scan_papers_returns_pdf_records() -> None:
    workspace = make_workspace("scanner-records")
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    papers_dir.mkdir()
    notes_dir.mkdir()
    (papers_dir / "Example Paper.pdf").write_bytes(b"%PDF-1.4\n")
    (papers_dir / "ignore.txt").write_text("not a pdf", encoding="utf-8")

    records = scan_papers(papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(records) == 1
    record = records[0]
    assert record["filename"] == "Example Paper.pdf"
    assert record["title"] == "Example Paper"
    assert record["authors"] == ""
    assert record["year"] == ""
    assert record["journal"] == ""
    assert record["doi"] == ""
    assert record["doi_source"] == ""
    assert record["doi_extracted_at"] == ""
    assert record["tags"] == ""
    assert record["status"] == "unread"
    assert record["reading_priority"] == "normal"
    assert record["metadata_source"] == ""
    assert record["metadata_confidence"] == ""
    assert record["metadata_checked_at"] == ""
    assert record["paper_id"].startswith("example-paper-")
    assert record["note_path"].endswith(".md")


def test_scan_papers_uses_stable_ids() -> None:
    workspace = make_workspace("scanner-stable")
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    papers_dir.mkdir()
    notes_dir.mkdir()
    (papers_dir / "Stable.pdf").write_bytes(b"%PDF-1.4\n")

    first = scan_papers(papers_dir=papers_dir, notes_dir=notes_dir)
    second = scan_papers(papers_dir=papers_dir, notes_dir=notes_dir)

    assert first[0]["paper_id"] == second[0]["paper_id"]
