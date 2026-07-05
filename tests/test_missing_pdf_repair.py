import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from services.missing_pdf_repair import (
    ARCHIVE_DEFERRED_MESSAGE,
    MissingPDFRepairError,
    build_reconnect_plan,
    list_reconnect_candidates,
    reconnect_missing_pdf,
    remove_missing_pdf_from_index,
)
from storage.index_store import load_index, save_index
from tests.helpers import make_workspace


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _workspace(name: str) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    workspace = make_workspace(name)
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    note_blocks_dir = workspace / "data" / "note_blocks"
    extracted_text_dir = workspace / "data" / "extracted_text"
    projects_dir = workspace / "data" / "projects"
    index_csv = workspace / "data" / "paper_index.csv"
    for directory in (papers_dir, notes_dir, note_blocks_dir, extracted_text_dir, projects_dir):
        directory.mkdir(parents=True)
    return workspace, papers_dir, notes_dir, note_blocks_dir, extracted_text_dir, projects_dir, index_csv


def _missing_record(missing_pdf: Path, contents: bytes, **overrides: str) -> dict[str, str]:
    record = {
        "paper_id": "stable-paper-id",
        "filename": missing_pdf.name,
        "filepath": str(missing_pdf.resolve(strict=False)),
        "pdf_sha256": _sha256(contents),
        "title": "Stable Paper",
        "authors": "Author Name",
        "year": "2024",
        "status": "reading",
        "reading_priority": "high",
        "note_path": str((missing_pdf.parent.parent / "notes" / "stable-paper-id.md").resolve(strict=False)),
    }
    record.update(overrides)
    return record


def test_reconnect_candidates_prefer_matching_pdf_sha256() -> None:
    _, papers_dir, *_rest, index_csv = _workspace("repair-candidates")
    original_contents = b"%PDF-1.4\noriginal"
    mismatch_contents = b"%PDF-1.4\nother"
    missing_pdf = papers_dir / "Missing.pdf"
    matching_pdf = papers_dir / "Matching.pdf"
    mismatch_pdf = papers_dir / "Mismatch.pdf"
    matching_pdf.write_bytes(original_contents)
    mismatch_pdf.write_bytes(mismatch_contents)
    record = _missing_record(missing_pdf, original_contents)
    save_index(pd.DataFrame([record]), index_csv)

    candidates = list_reconnect_candidates(record, index_csv=index_csv, papers_dir=papers_dir)

    assert candidates[0]["path"] == str(matching_pdf.resolve())
    assert candidates[0]["status"] == "hash_match"
    assert candidates[0]["requires_hash_mismatch_confirmation"] is False
    mismatch = next(candidate for candidate in candidates if candidate["path"] == str(mismatch_pdf.resolve()))
    assert mismatch["status"] == "hash_mismatch"
    assert mismatch["requires_hash_mismatch_confirmation"] is True


def test_reconnect_matching_hash_preserves_paper_id_and_identity_files() -> None:
    (
        _,
        papers_dir,
        notes_dir,
        note_blocks_dir,
        extracted_text_dir,
        projects_dir,
        index_csv,
    ) = _workspace("repair-reconnect-match")
    contents = b"%PDF-1.4\nstable"
    missing_pdf = papers_dir / "Missing.pdf"
    target_pdf = papers_dir / "Reconnected.pdf"
    target_pdf.write_bytes(contents)
    paper_id = "stable-paper-id"
    note_path = notes_dir / f"{paper_id}.md"
    note_block_path = note_blocks_dir / f"{paper_id}.json"
    extracted_text_path = extracted_text_dir / f"{paper_id}.txt"
    project_links_path = projects_dir / "project_links.json"
    note_path.write_text("note sentinel", encoding="utf-8")
    note_block_path.write_text("[]", encoding="utf-8")
    extracted_text_path.write_text("cache sentinel", encoding="utf-8")
    project_links_path.write_text(
        json.dumps([{"id": "link-1", "paper_id": paper_id, "target_type": "paper", "target_id": paper_id}]),
        encoding="utf-8",
    )
    save_index(
        pd.DataFrame(
            [
                _missing_record(
                    missing_pdf,
                    contents,
                    paper_id=paper_id,
                    note_path=str(note_path.resolve()),
                )
            ]
        ),
        index_csv,
    )
    before = load_index(index_csv).iloc[0].to_dict()

    result = reconnect_missing_pdf(paper_id, target_pdf, index_csv=index_csv, papers_dir=papers_dir)

    row = load_index(index_csv).iloc[0]
    assert result["status"] == "reconnected"
    assert row["paper_id"] == paper_id
    assert row["filename"] == target_pdf.name
    assert row["filepath"] == str(target_pdf.resolve())
    assert row["pdf_sha256"] == _sha256(contents)
    assert row["title"] == before["title"]
    assert row["status"] == before["status"]
    assert row["reading_priority"] == before["reading_priority"]
    assert row["note_path"] == str(note_path.resolve())
    assert note_path.read_text(encoding="utf-8") == "note sentinel"
    assert note_block_path.read_text(encoding="utf-8") == "[]"
    assert extracted_text_path.read_text(encoding="utf-8") == "cache sentinel"
    assert paper_id in project_links_path.read_text(encoding="utf-8")


def test_reconnect_hash_mismatch_requires_explicit_confirmation() -> None:
    _, papers_dir, *_rest, index_csv = _workspace("repair-reconnect-mismatch")
    original_contents = b"%PDF-1.4\noriginal"
    replacement_contents = b"%PDF-1.4\nreplacement"
    missing_pdf = papers_dir / "Missing.pdf"
    replacement_pdf = papers_dir / "Replacement.pdf"
    replacement_pdf.write_bytes(replacement_contents)
    save_index(pd.DataFrame([_missing_record(missing_pdf, original_contents)]), index_csv)
    original_index_bytes = index_csv.read_bytes()

    plan = build_reconnect_plan("stable-paper-id", replacement_pdf, index_csv=index_csv, papers_dir=papers_dir)

    assert plan["status"] == "hash_mismatch"
    assert plan["requires_hash_mismatch_confirmation"] is True
    with pytest.raises(MissingPDFRepairError, match="Hash mismatch requires explicit confirmation"):
        reconnect_missing_pdf("stable-paper-id", replacement_pdf, index_csv=index_csv, papers_dir=papers_dir)
    assert index_csv.read_bytes() == original_index_bytes

    reconnect_missing_pdf(
        "stable-paper-id",
        replacement_pdf,
        index_csv=index_csv,
        papers_dir=papers_dir,
        confirm_hash_mismatch=True,
    )
    row = load_index(index_csv).iloc[0]
    assert row["paper_id"] == "stable-paper-id"
    assert row["filename"] == replacement_pdf.name
    assert row["pdf_sha256"] == _sha256(replacement_contents)


def test_reconnect_rejects_target_already_indexed_to_another_paper() -> None:
    _, papers_dir, *_rest, index_csv = _workspace("repair-reconnect-indexed-target")
    missing_contents = b"%PDF-1.4\nmissing"
    target_contents = b"%PDF-1.4\ntarget"
    missing_pdf = papers_dir / "Missing.pdf"
    target_pdf = papers_dir / "Already Indexed.pdf"
    target_pdf.write_bytes(target_contents)
    save_index(
        pd.DataFrame(
            [
                _missing_record(missing_pdf, missing_contents),
                {
                    "paper_id": "other-paper-id",
                    "filename": target_pdf.name,
                    "filepath": str(target_pdf.resolve()),
                    "pdf_sha256": _sha256(target_contents),
                    "title": "Other",
                },
            ]
        ),
        index_csv,
    )

    with pytest.raises(MissingPDFRepairError) as exc_info:
        reconnect_missing_pdf(
            "stable-paper-id",
            target_pdf,
            index_csv=index_csv,
            papers_dir=papers_dir,
            confirm_hash_mismatch=True,
        )

    assert exc_info.value.plan["status"] == "already_indexed"
    assert set(load_index(index_csv)["paper_id"]) == {"stable-paper-id", "other-paper-id"}


def test_remove_from_index_requires_confirmation_and_deletes_only_index_row() -> None:
    _, papers_dir, notes_dir, note_blocks_dir, extracted_text_dir, projects_dir, index_csv = _workspace("repair-remove")
    contents = b"%PDF-1.4\nmissing"
    missing_pdf = papers_dir / "Missing.pdf"
    paper_id = "stable-paper-id"
    note_path = notes_dir / f"{paper_id}.md"
    note_block_path = note_blocks_dir / f"{paper_id}.json"
    extracted_text_path = extracted_text_dir / f"{paper_id}.txt"
    projects_path = projects_dir / "projects.json"
    project_links_path = projects_dir / "project_links.json"
    for path, text in (
        (note_path, "note"),
        (note_block_path, "[]"),
        (extracted_text_path, "cache"),
        (projects_path, "[]"),
        (project_links_path, json.dumps([{"id": "link-1", "paper_id": paper_id}])),
    ):
        path.write_text(text, encoding="utf-8")
    save_index(
        pd.DataFrame([_missing_record(missing_pdf, contents, note_path=str(note_path.resolve()))]),
        index_csv,
    )

    with pytest.raises(MissingPDFRepairError, match="requires explicit confirmation"):
        remove_missing_pdf_from_index(paper_id, index_csv=index_csv, papers_dir=papers_dir)

    result = remove_missing_pdf_from_index(paper_id, index_csv=index_csv, papers_dir=papers_dir, confirm=True)

    assert result["status"] == "removed_from_index"
    assert load_index(index_csv).empty
    assert note_path.read_text(encoding="utf-8") == "note"
    assert note_block_path.read_text(encoding="utf-8") == "[]"
    assert extracted_text_path.read_text(encoding="utf-8") == "cache"
    assert projects_path.read_text(encoding="utf-8") == "[]"
    assert paper_id in project_links_path.read_text(encoding="utf-8")


def test_archive_missing_pdf_is_documented_as_deferred() -> None:
    assert "deferred" in ARCHIVE_DEFERRED_MESSAGE.lower()
