import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from services.library_health import (
    OrphanProjectLinkRepairError,
    build_orphan_project_link_removal_plan,
    remove_orphan_project_link,
    run_library_health_check,
)
from storage.project_link_store import create_project_link, list_project_links
from storage.project_store import create_project
from tests.helpers import make_workspace


def _workspace(name: str) -> tuple[Path, Path, Path, Path, Path, Path]:
    workspace = make_workspace(name)
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    note_blocks_dir = workspace / "data" / "note_blocks"
    projects_dir = workspace / "data" / "projects"
    extracted_text_dir = workspace / "data" / "extracted_text"
    index_csv = workspace / "data" / "paper_index.csv"
    for directory in (papers_dir, notes_dir, note_blocks_dir, projects_dir, extracted_text_dir):
        directory.mkdir(parents=True)
    return papers_dir, notes_dir, note_blocks_dir, projects_dir, extracted_text_dir, index_csv


def _run_health(paths: tuple[Path, Path, Path, Path, Path, Path]):
    papers_dir, notes_dir, note_blocks_dir, projects_dir, extracted_text_dir, index_csv = paths
    return run_library_health_check(
        index_csv=index_csv,
        papers_dir=papers_dir,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
        extracted_text_dir=extracted_text_dir,
    )


def _record(paper_id: str, pdf_path: Path, doi: str = "", **overrides: str) -> dict[str, str]:
    record = {
        "paper_id": paper_id,
        "filename": pdf_path.name,
        "filepath": str(pdf_path.resolve()),
        "title": f"Title {paper_id}",
        "authors": "Author Name",
        "year": "2024",
        "doi": doi,
    }
    record.update(overrides)
    return record


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def test_health_check_detects_missing_indexed_pdf() -> None:
    paths = _workspace("health-missing-pdf")
    index_csv = paths[-1]
    missing_pdf = paths[0] / "Missing.pdf"
    pd.DataFrame([_record("paper-1", missing_pdf)]).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert report["healthy"] is False
    assert report["missing_pdfs"] == [
        {
            "paper_id": "paper-1",
            "filename": "Missing.pdf",
            "filepath": str(missing_pdf.resolve()),
            "pdf_sha256": "",
        }
    ]


def test_health_check_detects_unindexed_pdf() -> None:
    paths = _workspace("health-unindexed-pdf")
    papers_dir, *_, index_csv = paths
    unindexed = papers_dir / "Unindexed.pdf"
    unindexed.write_bytes(b"%PDF-1.4\n")
    pd.DataFrame(columns=["paper_id", "filename", "filepath", "title", "authors", "year", "doi"]).to_csv(
        index_csv, index=False
    )

    report = _run_health(paths)

    assert report["unindexed_pdfs"] == [str(unindexed.resolve())]


def test_health_check_detects_normalized_duplicate_doi() -> None:
    paths = _workspace("health-duplicate-doi")
    papers_dir, *_, index_csv = paths
    first_pdf = papers_dir / "First.pdf"
    second_pdf = papers_dir / "Second.pdf"
    first_pdf.write_bytes(b"%PDF-1.4\nfirst")
    second_pdf.write_bytes(b"%PDF-1.4\nsecond")
    pd.DataFrame(
        [
            _record("paper-1", first_pdf, "10.1000/ABC"),
            _record("paper-2", second_pdf, "https://doi.org/10.1000/abc"),
        ]
    ).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert report["duplicate_dois"] == [
        {
            "doi": "10.1000/abc",
            "count": 2,
            "paper_ids": "paper-1, paper-2",
        }
    ]


def test_health_check_classifies_same_hash_among_multiple_indexed_records() -> None:
    paths = _workspace("health-duplicate-indexed")
    papers_dir, notes_dir, note_blocks_dir, projects_dir, _extracted_text_dir, index_csv = paths
    contents = b"%PDF-1.4\nsame indexed content"
    first_pdf = papers_dir / "First.pdf"
    second_pdf = papers_dir / "Second.pdf"
    first_pdf.write_bytes(contents)
    second_pdf.write_bytes(contents)
    note_path = notes_dir / "paper-1.md"
    note_path.write_text("# Note", encoding="utf-8")
    (note_blocks_dir / "paper-1.json").write_text(
        json.dumps([{"id": "block-1"}, {"id": "block-2"}]),
        encoding="utf-8",
    )
    (projects_dir / "projects.json").write_text(json.dumps([{"id": "project-1"}]), encoding="utf-8")
    (projects_dir / "project_links.json").write_text(
        json.dumps(
            [
                {"id": "link-1", "project_id": "project-1", "paper_id": "paper-1"},
                {"id": "link-2", "project_id": "project-1", "paper_id": "paper-1"},
            ]
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            _record("paper-1", first_pdf, status="reading", note_path=str(note_path.resolve())),
            _record("paper-2", second_pdf, status="read"),
        ]
    ).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert report["duplicate_pdf_hashes"] == [
        {
            "pdf_sha256": _sha256(contents),
            "classification": "indexed duplicate",
            "indexed_record_count": 2,
            "unindexed_file_count": 0,
            "indexed_records": [
                {
                    "paper_id": "paper-1",
                    "title": "Title paper-1",
                    "filename": "First.pdf",
                    "filepath": str(first_pdf.resolve()),
                    "status": "reading",
                    "note_path": str(note_path.resolve()),
                    "note_file_count": 1,
                    "note_block_count": 2,
                    "project_link_count": 2,
                },
                {
                    "paper_id": "paper-2",
                    "title": "Title paper-2",
                    "filename": "Second.pdf",
                    "filepath": str(second_pdf.resolve()),
                    "status": "read",
                    "note_path": str((notes_dir / "paper-2.md").resolve()),
                    "note_file_count": 0,
                    "note_block_count": 0,
                    "project_link_count": 0,
                },
            ],
            "unindexed_files": [],
        }
    ]


def test_health_check_classifies_same_hash_between_indexed_and_unindexed_pdfs() -> None:
    paths = _workspace("health-duplicate-pdf-hash")
    papers_dir, *_, index_csv = paths
    contents = b"%PDF-1.4\nsame content"
    indexed_pdf = papers_dir / "Indexed.pdf"
    duplicate_pdf = papers_dir / "Duplicate.pdf"
    indexed_pdf.write_bytes(contents)
    duplicate_pdf.write_bytes(contents)
    record = _record("paper-1", indexed_pdf, status="reading")
    record["pdf_sha256"] = _sha256(contents)
    pd.DataFrame([record]).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert report["unindexed_pdfs"] == [str(duplicate_pdf.resolve())]
    assert report["duplicate_pdf_hashes"] == [
        {
            "pdf_sha256": _sha256(contents),
            "classification": "indexed + unindexed duplicate",
            "indexed_record_count": 1,
            "unindexed_file_count": 1,
            "indexed_records": [
                {
                    "paper_id": "paper-1",
                    "title": "Title paper-1",
                    "filename": "Indexed.pdf",
                    "filepath": str(indexed_pdf.resolve()),
                    "status": "reading",
                    "note_path": str((paths[1] / "paper-1.md").resolve()),
                    "note_file_count": 0,
                    "note_block_count": 0,
                    "project_link_count": 0,
                }
            ],
            "unindexed_files": [
                {
                    "filename": "Duplicate.pdf",
                    "filepath": str(duplicate_pdf.resolve()),
                    "review_action": "Do not add to index yet; handle later.",
                }
            ],
        }
    ]


def test_health_check_classifies_same_hash_among_multiple_unindexed_pdfs() -> None:
    paths = _workspace("health-duplicate-unindexed")
    papers_dir, *_, index_csv = paths
    contents = b"%PDF-1.4\nsame unindexed content"
    first_pdf = papers_dir / "First.pdf"
    second_pdf = papers_dir / "Second.pdf"
    first_pdf.write_bytes(contents)
    second_pdf.write_bytes(contents)
    pd.DataFrame(columns=["paper_id", "filename", "filepath", "title", "authors", "year", "doi"]).to_csv(
        index_csv, index=False
    )

    report = _run_health(paths)

    assert report["duplicate_pdf_hashes"] == [
        {
            "pdf_sha256": _sha256(contents),
            "classification": "multiple unindexed duplicate",
            "indexed_record_count": 0,
            "unindexed_file_count": 2,
            "indexed_records": [],
            "unindexed_files": [
                {
                    "filename": "First.pdf",
                    "filepath": str(first_pdf.resolve()),
                    "review_action": "Do not add to index yet; handle later.",
                },
                {
                    "filename": "Second.pdf",
                    "filepath": str(second_pdf.resolve()),
                    "review_action": "Do not add to index yet; handle later.",
                },
            ],
        }
    ]


def test_duplicate_pdf_review_does_not_mutate_index_files_notes_or_project_links() -> None:
    paths = _workspace("health-duplicate-no-mutation")
    papers_dir, notes_dir, note_blocks_dir, projects_dir, _extracted_text_dir, index_csv = paths
    contents = b"%PDF-1.4\nsame content"
    indexed_pdf = papers_dir / "Indexed.pdf"
    duplicate_pdf = papers_dir / "Duplicate.pdf"
    indexed_pdf.write_bytes(contents)
    duplicate_pdf.write_bytes(contents)
    note_path = notes_dir / "paper-1.md"
    note_block_path = note_blocks_dir / "paper-1.json"
    project_links_path = projects_dir / "project_links.json"
    note_path.write_text("# Note", encoding="utf-8")
    note_block_path.write_text(json.dumps([{"id": "block-1"}]), encoding="utf-8")
    project_links_path.write_text(json.dumps([{"id": "link-1", "paper_id": "paper-1"}]), encoding="utf-8")
    pd.DataFrame(
        [_record("paper-1", indexed_pdf, status="reading", note_path=str(note_path.resolve()))]
    ).to_csv(index_csv, index=False)
    before_index = index_csv.read_bytes()
    before_note = note_path.read_text(encoding="utf-8")
    before_blocks = note_block_path.read_text(encoding="utf-8")
    before_links = project_links_path.read_text(encoding="utf-8")

    report = _run_health(paths)

    assert report["duplicate_pdf_hashes"][0]["classification"] == "indexed + unindexed duplicate"
    assert index_csv.read_bytes() == before_index
    assert indexed_pdf.exists()
    assert duplicate_pdf.exists()
    assert note_path.read_text(encoding="utf-8") == before_note
    assert note_block_path.read_text(encoding="utf-8") == before_blocks
    assert project_links_path.read_text(encoding="utf-8") == before_links


def test_health_check_detects_orphan_note_file() -> None:
    paths = _workspace("health-orphan-note")
    papers_dir, notes_dir, *_rest, index_csv = paths
    pdf_path = papers_dir / "Paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nindexed")
    (notes_dir / "paper-1.md").write_text("# Indexed note", encoding="utf-8")
    orphan_note = notes_dir / "missing-paper.md"
    orphan_note.write_text("# Orphan note", encoding="utf-8")
    pd.DataFrame([_record("paper-1", pdf_path)]).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert len(report["orphan_notes"]) == 1
    item = report["orphan_notes"][0]
    assert item["classification"] == "orphan note file"
    assert item["paper_id"] == "missing-paper"
    assert item["filename"] == "missing-paper.md"
    assert item["filepath"] == str(orphan_note.resolve())
    assert item["size_bytes"] > 0
    assert item["modified_at"]
    assert "Preserve for now" in item["review_action"]


def test_health_check_detects_orphan_note_block_file() -> None:
    paths = _workspace("health-orphan-note-block")
    papers_dir, _notes_dir, note_blocks_dir, _projects_dir, _extracted_text_dir, index_csv = paths
    pdf_path = papers_dir / "Paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nindexed")
    orphan_blocks = note_blocks_dir / "missing-paper.json"
    orphan_blocks.write_text(
        json.dumps(
            [
                {
                    "id": "block-1",
                    "paper_id": "missing-paper",
                    "block_type": "claim",
                    "title": "Detached claim",
                    "text": "This block is no longer attached to an indexed paper.",
                    "created_at": "2026-07-05T00:00:00+00:00",
                    "updated_at": "2026-07-05T00:00:01+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    pd.DataFrame([_record("paper-1", pdf_path)]).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert len(report["orphan_note_blocks"]) == 1
    item = report["orphan_note_blocks"][0]
    assert item["classification"] == "orphan note block file"
    assert item["paper_id"] == "missing-paper"
    assert item["filepath"] == str(orphan_blocks.resolve())
    assert item["block_count"] == 1
    assert item["block_ids"] == "block-1"
    assert item["blocks"] == [
        {
            "block_id": "block-1",
            "block_type": "claim",
            "title": "Detached claim",
            "text_preview": "This block is no longer attached to an indexed paper.",
            "created_at": "2026-07-05T00:00:00+00:00",
            "updated_at": "2026-07-05T00:00:01+00:00",
        }
    ]
    assert "Preserve for now" in item["review_action"]


def test_health_check_detects_orphan_project_link() -> None:
    paths = _workspace("health-orphan-project-link")
    papers_dir, _notes_dir, _note_blocks_dir, projects_dir, _extracted_text_dir, index_csv = paths
    pdf_path = papers_dir / "Paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nindexed")
    project = create_project("Live Project", base_dir=projects_dir)
    link = create_project_link(project["id"], "paper", "missing-paper", base_dir=projects_dir)
    pd.DataFrame([_record("paper-1", pdf_path)]).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert report["orphan_project_links"] == [
        {
            "classification": "orphan project link",
            "link_id": link["id"],
            "project_id": project["id"],
            "project_name": "Live Project",
            "target_type": "paper",
            "target_id": "missing-paper",
            "paper_id": "missing-paper",
            "link_type": "related",
            "note": "",
            "created_at": link["created_at"],
            "reason": "missing target paper",
            "review_action": "Remove only this project link after confirmation.",
        }
    ]


def test_remove_orphan_project_link_requires_confirmation_and_only_removes_link() -> None:
    paths = _workspace("health-orphan-project-link-remove")
    papers_dir, notes_dir, note_blocks_dir, projects_dir, _extracted_text_dir, index_csv = paths
    pdf_path = papers_dir / "Paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nindexed")
    note_path = notes_dir / "paper-1.md"
    note_block_path = note_blocks_dir / "paper-1.json"
    note_path.write_text("# Note", encoding="utf-8")
    note_block_path.write_text(json.dumps([{"id": "block-1", "paper_id": "paper-1"}]), encoding="utf-8")
    pd.DataFrame([_record("paper-1", pdf_path, note_path=str(note_path.resolve()))]).to_csv(index_csv, index=False)
    project = create_project("Live Project", base_dir=projects_dir)
    orphan = create_project_link(project["id"], "paper", "missing-paper", base_dir=projects_dir)
    valid = create_project_link(project["id"], "paper", "paper-1", link_type="background", base_dir=projects_dir)
    before_index = index_csv.read_bytes()
    before_pdf = pdf_path.read_bytes()
    before_note = note_path.read_text(encoding="utf-8")
    before_blocks = note_block_path.read_text(encoding="utf-8")

    plan = build_orphan_project_link_removal_plan(
        orphan["id"],
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
    )

    assert plan["status"] == "ready"
    assert plan["can_remove"] is True
    assert plan["removes"] == "project_link_only"
    with pytest.raises(OrphanProjectLinkRepairError, match="requires explicit confirmation"):
        remove_orphan_project_link(
            orphan["id"],
            index_csv=index_csv,
            note_blocks_dir=note_blocks_dir,
            projects_dir=projects_dir,
        )
    assert {link["id"] for link in list_project_links(projects_dir)} == {orphan["id"], valid["id"]}

    result = remove_orphan_project_link(
        orphan["id"],
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
        confirm=True,
    )

    assert result["status"] == "removed_project_link"
    assert [link["id"] for link in list_project_links(projects_dir)] == [valid["id"]]
    assert index_csv.read_bytes() == before_index
    assert pdf_path.read_bytes() == before_pdf
    assert note_path.read_text(encoding="utf-8") == before_note
    assert note_block_path.read_text(encoding="utf-8") == before_blocks


def test_orphan_review_does_not_mutate_notes_note_blocks_pdfs_or_index() -> None:
    paths = _workspace("health-orphan-no-mutation")
    papers_dir, notes_dir, note_blocks_dir, projects_dir, _extracted_text_dir, index_csv = paths
    pdf_path = papers_dir / "Paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nindexed")
    orphan_note = notes_dir / "missing-paper.md"
    orphan_blocks = note_blocks_dir / "missing-paper.json"
    orphan_note.write_text("# Detached note", encoding="utf-8")
    orphan_blocks.write_text(json.dumps([{"id": "block-1", "paper_id": "missing-paper"}]), encoding="utf-8")
    pd.DataFrame([_record("paper-1", pdf_path)]).to_csv(index_csv, index=False)
    project = create_project("Live Project", base_dir=projects_dir)
    orphan_link = create_project_link(project["id"], "paper", "missing-paper", base_dir=projects_dir)
    before_index = index_csv.read_bytes()
    before_pdf = pdf_path.read_bytes()
    before_note = orphan_note.read_text(encoding="utf-8")
    before_blocks = orphan_blocks.read_text(encoding="utf-8")

    report = _run_health(paths)

    assert report["orphan_notes"][0]["classification"] == "orphan note file"
    assert report["orphan_note_blocks"][0]["classification"] == "orphan note block file"
    assert report["orphan_project_links"][0]["classification"] == "orphan project link"
    assert index_csv.read_bytes() == before_index
    assert pdf_path.read_bytes() == before_pdf
    assert orphan_note.read_text(encoding="utf-8") == before_note
    assert orphan_blocks.read_text(encoding="utf-8") == before_blocks
    assert [link["id"] for link in list_project_links(projects_dir)] == [orphan_link["id"]]
