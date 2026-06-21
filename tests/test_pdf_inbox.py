from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from config.inbox import get_inbox_path
from ingest.scanner import scan_papers
from services.pdf_inbox import (
    ONLINE_ONLY_MESSAGE,
    PDFInboxError,
    build_inbox_import_plan,
    import_pdf_from_inbox,
    scan_pdf_inbox,
)
from storage.index_store import load_index, save_index
from tests.helpers import make_workspace


def _write_pdf(path: Path, marker: bytes = b"content") -> bytes:
    contents = b"%PDF-1.4\n" + marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    return contents


def _workspace(name: str) -> tuple[Path, Path, Path, Path, Path]:
    workspace = make_workspace(name)
    inbox_dir = workspace / "drive-inbox"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = workspace / "data" / "paper_index.csv"
    inbox_dir.mkdir()
    papers_dir.mkdir()
    notes_dir.mkdir()
    return workspace, inbox_dir, papers_dir, notes_dir, index_csv


def test_inbox_path_resolves_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("BLUEPRINT_INBOX_DIR", "G:\\My Drive\\BluePrint\\paper")

    assert get_inbox_path("ignored") == Path("G:\\My Drive\\BluePrint\\paper")


def test_inbox_path_uses_ui_value_when_environment_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("BLUEPRINT_INBOX_DIR", raising=False)

    assert get_inbox_path("C:\\Inbox") == Path("C:\\Inbox")
    assert get_inbox_path("") is None


def test_scan_lists_only_non_recursive_pdfs() -> None:
    _, inbox_dir, papers_dir, _, _ = _workspace("inbox-list")
    _write_pdf(inbox_dir / "Paper One.pdf")
    _write_pdf(inbox_dir / "UPPER.PDF", b"upper")
    (inbox_dir / "ignore.txt").write_text("ignore", encoding="utf-8")
    _write_pdf(inbox_dir / "nested" / "Nested.pdf", b"nested")

    result = scan_pdf_inbox(inbox_dir, papers_dir)

    assert result["status"] == "ok"
    assert [candidate["filename"] for candidate in result["candidates"]] == [
        "Paper One.pdf",
        "UPPER.PDF",
    ]
    assert all(candidate["status"] == "new" for candidate in result["candidates"])
    assert all(candidate["size_bytes"] > 0 for candidate in result["candidates"])
    assert all(candidate["modified_time"] for candidate in result["candidates"])


def test_scan_reports_missing_folder() -> None:
    workspace = make_workspace("inbox-missing")
    result = scan_pdf_inbox(workspace / "missing", workspace / "papers")

    assert result["status"] == "source_missing"
    assert result["candidates"] == []


def test_scan_rejects_blank_and_non_directory_paths() -> None:
    workspace = make_workspace("inbox-invalid")
    papers_dir = workspace / "papers"
    papers_dir.mkdir()
    not_a_folder = workspace / "file.txt"
    not_a_folder.write_text("file", encoding="utf-8")

    assert scan_pdf_inbox(None, papers_dir)["status"] == "invalid_path"
    assert scan_pdf_inbox(not_a_folder, papers_dir)["status"] == "invalid_path"


def test_scan_rejects_papers_directory_or_child_as_inbox() -> None:
    workspace = make_workspace("inbox-is-papers")
    papers_dir = workspace / "papers"
    child_dir = papers_dir / "inbox"
    child_dir.mkdir(parents=True)

    same_result = scan_pdf_inbox(papers_dir, papers_dir)
    child_result = scan_pdf_inbox(child_dir, papers_dir)

    assert same_result["status"] == "invalid_path"
    assert child_result["status"] == "invalid_path"
    assert "only managed PDF directory" in same_result["message"]


def test_same_filename_and_content_is_already_imported() -> None:
    _, inbox_dir, papers_dir, _, _ = _workspace("inbox-already-filename")
    contents = _write_pdf(inbox_dir / "Same.pdf")
    (papers_dir / "Same.pdf").write_bytes(contents)

    candidate = scan_pdf_inbox(inbox_dir, papers_dir)["candidates"][0]

    assert candidate["status"] == "already_imported"
    assert candidate["can_import"] is False


def test_same_hash_under_another_filename_is_already_imported() -> None:
    _, inbox_dir, papers_dir, _, _ = _workspace("inbox-already-hash")
    contents = _write_pdf(inbox_dir / "Inbox Name.pdf")
    (papers_dir / "Library Name.pdf").write_bytes(contents)

    candidate = scan_pdf_inbox(inbox_dir, papers_dir)["candidates"][0]

    assert candidate["status"] == "already_imported"
    assert candidate["can_import"] is False


def test_different_file_with_same_filename_is_collision() -> None:
    _, inbox_dir, papers_dir, _, _ = _workspace("inbox-collision")
    _write_pdf(inbox_dir / "Collision.pdf", b"inbox")
    library_contents = _write_pdf(papers_dir / "Collision.pdf", b"library")

    candidate = scan_pdf_inbox(inbox_dir, papers_dir)["candidates"][0]

    assert candidate["status"] == "filename_collision"
    assert candidate["can_import"] is False
    assert (papers_dir / "Collision.pdf").read_bytes() == library_contents


def test_incomplete_pdf_is_unreadable() -> None:
    _, inbox_dir, papers_dir, _, _ = _workspace("inbox-incomplete")
    (inbox_dir / "Incomplete.pdf").write_bytes(b"")

    candidate = scan_pdf_inbox(inbox_dir, papers_dir)["candidates"][0]

    assert candidate["status"] == "unreadable"
    assert candidate["can_import"] is False


def test_online_only_read_failure_has_actionable_message(monkeypatch) -> None:
    _, inbox_dir, papers_dir, _, _ = _workspace("inbox-online-only")
    source = inbox_dir / "Online.pdf"
    _write_pdf(source)
    monkeypatch.setattr("services.pdf_inbox._source_details", lambda path: ({}, ONLINE_ONLY_MESSAGE))

    candidate = scan_pdf_inbox(inbox_dir, papers_dir)["candidates"][0]

    assert candidate["status"] == "unreadable"
    assert candidate["message"] == ONLINE_ONLY_MESSAGE


def test_import_copies_source_and_uses_existing_index_workflow() -> None:
    _, inbox_dir, papers_dir, notes_dir, index_csv = _workspace("inbox-import")
    source = inbox_dir / "Imported.pdf"
    source_contents = _write_pdf(source, b"import me")

    result = import_pdf_from_inbox(
        source,
        inbox_dir,
        papers_dir=papers_dir,
        index_csv=index_csv,
        notes_dir=notes_dir,
    )

    target = papers_dir / "Imported.pdf"
    dataframe = load_index(index_csv)
    assert result["status"] == "imported"
    assert result["indexed"] is True
    assert source.read_bytes() == source_contents
    assert target.read_bytes() == source_contents
    assert len(dataframe) == 1
    assert dataframe.iloc[0]["filename"] == "Imported.pdf"
    assert Path(dataframe.iloc[0]["filepath"]).resolve().is_relative_to(papers_dir.resolve())
    assert Path(dataframe.iloc[0]["filepath"]).resolve() != source.resolve()
    assert dataframe.iloc[0]["paper_id"] == result["paper_id"]


def test_collision_blocks_import_without_overwrite() -> None:
    _, inbox_dir, papers_dir, notes_dir, index_csv = _workspace("inbox-block-overwrite")
    source = inbox_dir / "Collision.pdf"
    _write_pdf(source, b"inbox")
    target_contents = _write_pdf(papers_dir / "Collision.pdf", b"keep target")

    with pytest.raises(PDFInboxError, match="filename_collision"):
        import_pdf_from_inbox(source, inbox_dir, papers_dir, index_csv, notes_dir)

    assert source.exists()
    assert (papers_dir / "Collision.pdf").read_bytes() == target_contents
    assert not index_csv.exists()


def test_source_missing_after_preview_fails_safely() -> None:
    _, inbox_dir, papers_dir, notes_dir, index_csv = _workspace("inbox-stale-preview")
    source = inbox_dir / "Gone.pdf"
    _write_pdf(source)
    preview = build_inbox_import_plan(source, inbox_dir, papers_dir)
    assert preview["can_import"] is True
    source.unlink()

    with pytest.raises(PDFInboxError) as exc_info:
        import_pdf_from_inbox(source, inbox_dir, papers_dir, index_csv, notes_dir)

    assert exc_info.value.plan["status"] == "source_missing"
    assert not (papers_dir / "Gone.pdf").exists()
    assert not index_csv.exists()


def test_copy_failure_does_not_update_index(monkeypatch) -> None:
    _, inbox_dir, papers_dir, notes_dir, index_csv = _workspace("inbox-copy-failure")
    source = inbox_dir / "Failure.pdf"
    _write_pdf(source)
    updater = Mock()
    monkeypatch.setattr("services.pdf_inbox._copy_exclusive", Mock(side_effect=OSError("copy failed")))

    with pytest.raises(PDFInboxError, match="copy failed"):
        import_pdf_from_inbox(
            source,
            inbox_dir,
            papers_dir,
            index_csv,
            notes_dir,
            index_updater=updater,
        )

    updater.assert_not_called()
    assert source.exists()
    assert not (papers_dir / "Failure.pdf").exists()


def test_racing_target_is_not_deleted_or_overwritten(monkeypatch) -> None:
    _, inbox_dir, papers_dir, notes_dir, index_csv = _workspace("inbox-race")
    source = inbox_dir / "Race.pdf"
    _write_pdf(source, b"source")
    target = papers_dir / "Race.pdf"
    updater = Mock()

    def create_competing_target(source_path: Path, target_path: Path) -> None:
        target_path.write_bytes(b"competing target")
        raise FileExistsError("target appeared")

    monkeypatch.setattr("services.pdf_inbox._copy_exclusive", create_competing_target)

    with pytest.raises(PDFInboxError) as exc_info:
        import_pdf_from_inbox(
            source,
            inbox_dir,
            papers_dir,
            index_csv,
            notes_dir,
            index_updater=updater,
        )

    assert target.read_bytes() == b"competing target"
    assert exc_info.value.plan["status"] == "filename_collision"
    updater.assert_not_called()


def test_import_scan_preserves_existing_paper_ids_and_canonical_paths() -> None:
    _, inbox_dir, papers_dir, notes_dir, index_csv = _workspace("inbox-id-safety")
    existing_pdf = papers_dir / "Existing.pdf"
    _write_pdf(existing_pdf, b"existing")
    stable_id = "existing-stable-paper-id"
    save_index(
        pd.DataFrame(
            [
                {
                    "paper_id": stable_id,
                    "filename": existing_pdf.name,
                    "filepath": str(existing_pdf.resolve()),
                    "title": "Existing",
                }
            ]
        ),
        index_csv,
    )
    source = inbox_dir / "New Paper.pdf"
    _write_pdf(source, b"new")

    import_pdf_from_inbox(source, inbox_dir, papers_dir, index_csv, notes_dir)

    dataframe = load_index(index_csv)
    assert dataframe.loc[dataframe["filename"] == "Existing.pdf", "paper_id"].iloc[0] == stable_id
    assert len(dataframe) == 2
    assert all(
        Path(filepath).resolve().is_relative_to(papers_dir.resolve())
        for filepath in dataframe["filepath"]
    )
    assert all(Path(filepath).resolve() != source.resolve() for filepath in dataframe["filepath"])


def test_direct_papers_scan_still_works() -> None:
    _, _, papers_dir, notes_dir, _ = _workspace("direct-papers-scan")
    _write_pdf(papers_dir / "Direct.pdf")

    records = scan_papers(papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(records) == 1
    assert records[0]["filename"] == "Direct.pdf"
    assert Path(records[0]["filepath"]).resolve().is_relative_to(papers_dir.resolve())
