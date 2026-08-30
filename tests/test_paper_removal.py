from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from services.paper_metadata_mutation import paper_lifecycle_revision, paper_pdf_revision
from services.paper_removal import PaperRemovalConflict, PaperRemovalService
from storage.index_store import INDEX_COLUMNS, read_index_snapshot, save_index


PDF_BYTES = b"%PDF-1.4\n% safe removal test PDF\n"


def _workspace(tmp_path: Path) -> tuple[PaperRemovalService, Path, Path, str]:
    papers = tmp_path / "papers"
    notes = tmp_path / "notes"
    blocks = tmp_path / "data" / "note_blocks"
    projects = tmp_path / "data" / "projects"
    index = tmp_path / "data" / "paper_index.csv"
    papers.mkdir()
    notes.mkdir()
    blocks.mkdir(parents=True)
    projects.mkdir()
    paper_id = "paper-1"
    pdf = papers / "safe.pdf"
    pdf.write_bytes(PDF_BYTES)
    record = {column: "" for column in INDEX_COLUMNS}
    record.update(
        {
            "paper_id": paper_id,
            "filename": pdf.name,
            "filepath": str(pdf.resolve()),
            "title": "Kept metadata",
            "status": "reading",
            "is_archived": "false",
        }
    )
    save_index(pd.DataFrame([record]), index)
    (notes / f"{paper_id}.md").write_text("saved note", encoding="utf-8")
    (blocks / f"{paper_id}.json").write_text('[{"id":"block-1","paper_id":"paper-1"}]', encoding="utf-8")
    (projects / "links.json").write_text('[{"paper_id":"paper-1","project_id":"project-1"}]', encoding="utf-8")
    return PaperRemovalService(index_csv=index, papers_dir=papers), pdf, index, paper_id


def test_remove_managed_pdf_creates_verified_recovery_and_preserves_paper_owned_state(tmp_path: Path) -> None:
    service, pdf, index, paper_id = _workspace(tmp_path)
    owned_paths = [
        tmp_path / "notes" / f"{paper_id}.md",
        tmp_path / "data" / "note_blocks" / f"{paper_id}.json",
        tmp_path / "data" / "projects" / "links.json",
    ]
    before_owned = {path: path.read_bytes() for path in owned_paths}
    record = read_index_snapshot(index).iloc[0].fillna("").to_dict()

    result = service.remove_managed_pdf(paper_id, paper_pdf_revision(record))

    assert result.status == "removed"
    assert result.recovery_copy_created is True
    assert not pdf.exists()
    assert {path: path.read_bytes() for path in owned_paths} == before_owned
    persisted = read_index_snapshot(index).iloc[0]
    assert persisted["paper_id"] == paper_id
    assert persisted["title"] == "Kept metadata"
    manifests = list((tmp_path / "exports" / "recovery").glob("*.manifest.json"))
    assert len(manifests) == 1
    assert "safe.pdf" in manifests[0].read_text(encoding="utf-8")


def test_archive_paper_preserves_pdf_and_rejects_stale_lifecycle_revision(tmp_path: Path) -> None:
    service, pdf, index, paper_id = _workspace(tmp_path)
    record = read_index_snapshot(index).iloc[0].fillna("").to_dict()

    with pytest.raises(PaperRemovalConflict):
        service.archive_paper(paper_id, "0" * 64)
    assert pdf.exists()
    assert read_index_snapshot(index).iloc[0]["is_archived"] == "false"

    result = service.archive_paper(paper_id, paper_lifecycle_revision(record))
    assert result.status == "archived"
    assert pdf.exists()
    persisted = read_index_snapshot(index).iloc[0]
    assert persisted["is_archived"] == "true"
    assert persisted["paper_id"] == paper_id
