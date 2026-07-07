import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from services.file_lifecycle import (
    FileLifecycleRepairError,
    build_duplicate_remove_plan,
    diagnose_file_lifecycle,
    reconnect_duplicate_pdf,
    remove_duplicate_index_row,
)
from storage.index_store import INDEX_COLUMNS, load_index, save_index, update_index_from_scan
from tests.helpers import make_workspace


def _workspace(name: str) -> tuple[Path, Path, Path, Path, Path, Path]:
    workspace = make_workspace(name)
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    note_blocks_dir = workspace / "data" / "note_blocks"
    extracted_text_dir = workspace / "data" / "extracted_text"
    projects_dir = workspace / "data" / "projects"
    index_csv = workspace / "data" / "paper_index.csv"
    for directory in (papers_dir, notes_dir, note_blocks_dir, extracted_text_dir, projects_dir):
        directory.mkdir(parents=True)
    return papers_dir, notes_dir, note_blocks_dir, extracted_text_dir, projects_dir, index_csv


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _record(paper_id: str, pdf_path: Path, contents: bytes, **overrides: str) -> dict[str, str]:
    record = {
        "paper_id": paper_id,
        "filename": pdf_path.name,
        "filepath": str(pdf_path.resolve(strict=False)),
        "pdf_sha256": _sha256(contents),
        "title": f"Title {paper_id}",
        "authors": "Author Name",
        "year": "2024",
        "status": "reading",
        "reading_priority": "normal",
        "note_path": str((pdf_path.parent.parent / "notes" / f"{paper_id}.md").resolve(strict=False)),
    }
    record.update(overrides)
    return record


def test_file_lifecycle_diagnosis_detects_same_hash_duplicates_without_mutation() -> None:
    papers_dir, *_rest, index_csv = _workspace("lifecycle-diagnosis-duplicates")
    contents = b"%PDF-1.4\nsame lifecycle content"
    indexed_pdf = papers_dir / "Indexed.pdf"
    unindexed_pdf = papers_dir / "Unindexed.pdf"
    indexed_pdf.write_bytes(contents)
    unindexed_pdf.write_bytes(contents)
    pd.DataFrame([_record("paper-1", indexed_pdf, contents)]).to_csv(index_csv, index=False)
    before_index = index_csv.read_bytes()

    report = diagnose_file_lifecycle(index_csv=index_csv, papers_dir=papers_dir)

    assert index_csv.read_bytes() == before_index
    assert report["same_hash_duplicate_candidates"] == [
        {
            "pdf_sha256": _sha256(contents),
            "indexed_records": [
                {
                    "paper_id": "paper-1",
                    "filename": "Indexed.pdf",
                    "filepath": str(indexed_pdf.resolve()),
                    "pdf_sha256": _sha256(contents),
                }
            ],
            "unindexed_files": [
                {
                    "filename": "Unindexed.pdf",
                    "filepath": str(unindexed_pdf.resolve()),
                    "pdf_sha256": _sha256(contents),
                }
            ],
            "indexed_record_count": 1,
            "unindexed_file_count": 1,
        }
    ]


def test_duplicate_reconnect_preserves_paper_id_and_user_data() -> None:
    papers_dir, notes_dir, note_blocks_dir, extracted_text_dir, projects_dir, index_csv = _workspace(
        "lifecycle-reconnect"
    )
    contents = b"%PDF-1.4\nsame lifecycle reconnect content"
    indexed_pdf = papers_dir / "Old.pdf"
    target_pdf = papers_dir / "Renamed.pdf"
    indexed_pdf.write_bytes(contents)
    target_pdf.write_bytes(contents)
    paper_id = "paper-1"
    note_path = notes_dir / f"{paper_id}.md"
    block_path = note_blocks_dir / f"{paper_id}.json"
    cache_path = extracted_text_dir / f"{paper_id}.txt"
    project_links_path = projects_dir / "project_links.json"
    note_path.write_text("note sentinel", encoding="utf-8")
    block_path.write_text("[]", encoding="utf-8")
    cache_path.write_text("cache sentinel", encoding="utf-8")
    project_links_path.write_text(json.dumps([{"id": "link-1", "paper_id": paper_id}]), encoding="utf-8")
    save_index(
        pd.DataFrame([_record(paper_id, indexed_pdf, contents, note_path=str(note_path.resolve()))]),
        index_csv,
    )
    before = load_index(index_csv).iloc[0].to_dict()

    result = reconnect_duplicate_pdf(paper_id, target_pdf, index_csv=index_csv, papers_dir=papers_dir)

    row = load_index(index_csv).iloc[0]
    assert result["status"] == "reconnected"
    assert row["paper_id"] == paper_id
    assert row["filename"] == target_pdf.name
    assert row["filepath"] == str(target_pdf.resolve())
    assert row["pdf_sha256"] == _sha256(contents)
    assert row["title"] == before["title"]
    assert row["note_path"] == str(note_path.resolve())
    assert indexed_pdf.exists()
    assert target_pdf.exists()
    assert note_path.read_text(encoding="utf-8") == "note sentinel"
    assert block_path.read_text(encoding="utf-8") == "[]"
    assert cache_path.read_text(encoding="utf-8") == "cache sentinel"
    assert paper_id in project_links_path.read_text(encoding="utf-8")


def test_duplicate_reconnect_hash_mismatch_requires_confirmation() -> None:
    papers_dir, *_rest, index_csv = _workspace("lifecycle-reconnect-mismatch")
    original = b"%PDF-1.4\noriginal"
    replacement = b"%PDF-1.4\nreplacement"
    indexed_pdf = papers_dir / "Original.pdf"
    target_pdf = papers_dir / "Replacement.pdf"
    indexed_pdf.write_bytes(original)
    target_pdf.write_bytes(replacement)
    save_index(pd.DataFrame([_record("paper-1", indexed_pdf, original)]), index_csv)
    before_index = index_csv.read_bytes()

    with pytest.raises(FileLifecycleRepairError, match="Hash mismatch requires explicit confirmation"):
        reconnect_duplicate_pdf("paper-1", target_pdf, index_csv=index_csv, papers_dir=papers_dir)
    assert index_csv.read_bytes() == before_index

    result = reconnect_duplicate_pdf(
        "paper-1",
        target_pdf,
        index_csv=index_csv,
        papers_dir=papers_dir,
        confirm_hash_mismatch=True,
    )

    assert result["status"] == "reconnected"
    assert load_index(index_csv).iloc[0]["pdf_sha256"] == _sha256(replacement)


def test_duplicate_remove_requires_confirmation_and_deletes_only_index_row() -> None:
    papers_dir, notes_dir, note_blocks_dir, extracted_text_dir, projects_dir, index_csv = _workspace(
        "lifecycle-remove"
    )
    contents = b"%PDF-1.4\nsame duplicate rows"
    first_pdf = papers_dir / "First.pdf"
    second_pdf = papers_dir / "Second.pdf"
    first_pdf.write_bytes(contents)
    second_pdf.write_bytes(contents)
    removed_id = "paper-1"
    kept_id = "paper-2"
    note_path = notes_dir / f"{removed_id}.md"
    block_path = note_blocks_dir / f"{removed_id}.json"
    cache_path = extracted_text_dir / f"{removed_id}.txt"
    project_links_path = projects_dir / "project_links.json"
    note_path.write_text("note", encoding="utf-8")
    block_path.write_text("[]", encoding="utf-8")
    cache_path.write_text("cache", encoding="utf-8")
    project_links_path.write_text(json.dumps([{"id": "link-1", "paper_id": removed_id}]), encoding="utf-8")
    save_index(
        pd.DataFrame(
            [
                _record(removed_id, first_pdf, contents, note_path=str(note_path.resolve())),
                _record(kept_id, second_pdf, contents),
            ]
        ),
        index_csv,
    )

    plan = build_duplicate_remove_plan(removed_id, index_csv=index_csv, papers_dir=papers_dir)
    assert plan["status"] == "ready"
    with pytest.raises(FileLifecycleRepairError, match="requires explicit confirmation"):
        remove_duplicate_index_row(removed_id, index_csv=index_csv, papers_dir=papers_dir)

    result = remove_duplicate_index_row(removed_id, index_csv=index_csv, papers_dir=papers_dir, confirm=True)

    assert result["status"] == "removed_duplicate_index_row"
    assert set(load_index(index_csv)["paper_id"]) == {kept_id}
    assert first_pdf.exists()
    assert second_pdf.exists()
    assert note_path.read_text(encoding="utf-8") == "note"
    assert block_path.read_text(encoding="utf-8") == "[]"
    assert cache_path.read_text(encoding="utf-8") == "cache"
    assert removed_id in project_links_path.read_text(encoding="utf-8")


def test_filename_path_rename_repair_is_diagnosed_and_reconnected() -> None:
    papers_dir, *_rest, index_csv = _workspace("lifecycle-rename-repair")
    contents = b"%PDF-1.4\nrenamed file"
    missing_pdf = papers_dir / "Old Name.pdf"
    renamed_pdf = papers_dir / "New Name.pdf"
    renamed_pdf.write_bytes(contents)
    save_index(pd.DataFrame([_record("paper-1", missing_pdf, contents)]), index_csv)

    report = diagnose_file_lifecycle(index_csv=index_csv, papers_dir=papers_dir)

    assert report["missing_indexed_pdfs"][0]["paper_id"] == "paper-1"
    assert report["likely_reconnect_candidates"] == [
        {
            "paper_id": "paper-1",
            "missing_filepath": str(missing_pdf.resolve(strict=False)),
            "candidate_filepath": str(renamed_pdf.resolve()),
            "candidate_filename": "New Name.pdf",
            "pdf_sha256": _sha256(contents),
            "reason": "same_pdf_sha256",
        }
    ]

    reconnect_duplicate_pdf("paper-1", renamed_pdf, index_csv=index_csv, papers_dir=papers_dir)
    row = load_index(index_csv).iloc[0]
    assert row["paper_id"] == "paper-1"
    assert row["filename"] == "New Name.pdf"
    assert row["filepath"] == str(renamed_pdf.resolve())


def test_index_consistency_before_and_after_duplicate_repair() -> None:
    papers_dir, *_rest, index_csv = _workspace("lifecycle-index-consistency")
    contents = b"%PDF-1.4\nconsistent duplicate rows"
    first_pdf = papers_dir / "First.pdf"
    second_pdf = papers_dir / "Second.pdf"
    first_pdf.write_bytes(contents)
    second_pdf.write_bytes(contents)
    save_index(pd.DataFrame([_record("paper-1", first_pdf, contents), _record("paper-2", second_pdf, contents)]), index_csv)
    before = load_index(index_csv)

    remove_duplicate_index_row("paper-2", index_csv=index_csv, papers_dir=papers_dir, confirm=True)
    after = load_index(index_csv)

    assert list(before.columns) == INDEX_COLUMNS
    assert list(after.columns) == INDEX_COLUMNS
    assert len(before) == 2
    assert len(after) == 1
    assert after.iloc[0]["paper_id"] == "paper-1"


def test_scan_does_not_auto_merge_existing_rows_with_same_hash() -> None:
    papers_dir, notes_dir, *_rest, index_csv = _workspace("lifecycle-no-auto-merge")
    contents = b"%PDF-1.4\nsame content remains separate"
    first_pdf = papers_dir / "First.pdf"
    second_pdf = papers_dir / "Second.pdf"
    first_pdf.write_bytes(contents)
    second_pdf.write_bytes(contents)
    save_index(
        pd.DataFrame([_record("paper-1", first_pdf, contents), _record("paper-2", second_pdf, contents)]),
        index_csv,
    )

    update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    updated = load_index(index_csv)

    assert len(updated) == 2
    assert set(updated["paper_id"]) == {"paper-1", "paper-2"}
    assert set(updated["pdf_sha256"]) == {_sha256(contents)}
