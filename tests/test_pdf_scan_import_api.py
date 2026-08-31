from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api import dependencies
from api.main import create_app
from api.pdf_files import resolve_managed_pdf
from services import library_read_model
from services.pdf_scan_import import PdfScanImportService
from services.reader_commands import ReaderCommandService
from storage.index_store import read_index_snapshot


PDF_BYTES = b"%PDF-1.4\n% disposable scan/import test PDF\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    papers_dir = tmp_path / "papers"
    notes_dir = tmp_path / "notes"
    index_csv = tmp_path / "data" / "paper_index.csv"
    papers_dir.mkdir()
    notes_dir.mkdir()
    return tmp_path, papers_dir, notes_dir, index_csv


def _client(
    workspace: Path,
    papers_dir: Path,
    notes_dir: Path,
    index_csv: Path,
) -> TestClient:
    application = create_app()
    scan_import = PdfScanImportService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        notes_dir=notes_dir,
    )
    reader_commands = ReaderCommandService(index_csv=index_csv, notes_dir=notes_dir)
    application.dependency_overrides[dependencies.get_pdf_scan_import_service] = lambda: scan_import
    application.dependency_overrides[dependencies.get_reader_command_service] = lambda: reader_commands
    application.dependency_overrides[dependencies.get_paper_list_items] = lambda: library_read_model.build_paper_list_items(
        index_csv=index_csv,
        health_report={},
    )
    application.dependency_overrides[dependencies.get_paper_detail] = lambda paper_id: library_read_model.build_paper_detail(
        paper_id,
        index_csv=index_csv,
        workspace_root=workspace,
        papers_dir=papers_dir,
        notes_dir=notes_dir,
        extracted_text_dir=workspace / "data" / "extracted_text",
        profile_dir=workspace / "data" / "paper_profiles",
        projects_dir=workspace / "data" / "projects",
        health_report={},
    )
    application.dependency_overrides[dependencies.get_reader_snapshot] = lambda paper_id: library_read_model.build_reader_snapshot(
        paper_id,
        index_csv=index_csv,
        notes_dir=notes_dir,
        workspace_root=workspace,
        papers_dir=papers_dir,
        extracted_text_dir=workspace / "data" / "extracted_text",
        profile_dir=workspace / "data" / "paper_profiles",
        projects_dir=workspace / "data" / "projects",
        health_report={},
    )
    application.dependency_overrides[dependencies.get_managed_pdf] = lambda paper_id: resolve_managed_pdf(
        paper_id,
        index_csv=index_csv,
        papers_dir=papers_dir,
    )
    return TestClient(application)


def test_scan_finds_new_pdf_without_creating_a_paper_and_ignores_non_pdfs(tmp_path: Path) -> None:
    workspace, papers_dir, notes_dir, index_csv = _workspace(tmp_path)
    (papers_dir / "nested").mkdir()
    (papers_dir / "nested" / "New.pdf").write_bytes(PDF_BYTES)
    (papers_dir / "not-a-paper.txt").write_text("not a PDF", encoding="utf-8")
    client = _client(workspace, papers_dir, notes_dir, index_csv)

    response = client.post("/papers/scan", json={})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "Found 1 managed PDF candidate(s).",
        "candidates": [
            {
                "relative_path": "nested/New.pdf",
                "filename": "New.pdf",
                "status": "new",
                "message": "Ready to register as a new Paper.",
                "can_import": True,
                "can_reconnect": False,
                "reconnect_paper_id": "",
                "size_bytes": len(PDF_BYTES),
            }
        ],
    }
    assert not index_csv.exists()
    assert str(tmp_path) not in response.text


def test_upload_registers_pdf_through_the_same_duplicate_safe_import_boundary(tmp_path: Path) -> None:
    workspace, papers_dir, notes_dir, index_csv = _workspace(tmp_path)
    client = _client(workspace, papers_dir, notes_dir, index_csv)

    uploaded = client.post(
        "/papers/upload",
        files=[("files", ("browser-upload.pdf", PDF_BYTES, "application/pdf"))],
    )

    assert uploaded.status_code == 200
    assert uploaded.json()["imported_count"] == 1
    assert uploaded.json()["results"][0]["status"] == "imported"
    duplicate = client.post(
        "/papers/upload",
        files=[("files", ("second-name.pdf", PDF_BYTES, "application/pdf"))],
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["results"][0]["status"] == "duplicate_content"
    assert len(read_index_snapshot(index_csv)) == 1
    assert not (papers_dir / "second-name.pdf").exists()

    rejected = client.post(
        "/papers/upload",
        files=[("files", ("not-a-pdf.txt", b"plain text", "text/plain"))],
    )
    assert rejected.status_code == 200
    assert rejected.json()["results"][0]["status"] == "invalid"


def test_scan_identifies_registered_and_content_duplicate_pdfs_without_new_rows(tmp_path: Path) -> None:
    workspace, papers_dir, notes_dir, index_csv = _workspace(tmp_path)
    (papers_dir / "Registered.pdf").write_bytes(PDF_BYTES)
    client = _client(workspace, papers_dir, notes_dir, index_csv)
    imported = client.post("/papers/import", json={"relative_paths": ["Registered.pdf"]})
    assert imported.status_code == 200
    assert imported.json()["imported_count"] == 1

    (papers_dir / "Same-content.pdf").write_bytes(PDF_BYTES)
    response = client.post("/papers/scan", json={})
    candidates = {item["relative_path"]: item for item in response.json()["candidates"]}

    assert candidates["Registered.pdf"]["status"] == "already_registered"
    assert candidates["Same-content.pdf"]["status"] == "duplicate_content"
    assert len(read_index_snapshot(index_csv)) == 1


def test_selected_import_registers_only_selected_pdf_and_opens_in_library_reader_and_metadata_workflow(tmp_path: Path) -> None:
    workspace, papers_dir, notes_dir, index_csv = _workspace(tmp_path)
    (papers_dir / "First.pdf").write_bytes(PDF_BYTES)
    (papers_dir / "Second.pdf").write_bytes(PDF_BYTES + b"second")
    client = _client(workspace, papers_dir, notes_dir, index_csv)

    preview = client.post("/papers/scan", json={})
    assert [item["status"] for item in preview.json()["candidates"]] == ["new", "new"]
    imported = client.post("/papers/import", json={"relative_paths": ["First.pdf"]})

    assert imported.status_code == 200
    result = imported.json()
    assert result["imported_count"] == 1
    paper_id = result["results"][0]["paper_id"]
    assert [record["filename"] for record in read_index_snapshot(index_csv).to_dict("records")] == ["First.pdf"]
    assert client.post("/papers/scan", json={}).json()["candidates"][1]["status"] == "new"

    library = client.get("/papers")
    reader = client.get(f"/papers/{paper_id}/reader")
    pdf = client.get(f"/papers/{paper_id}/pdf")
    assert library.status_code == 200
    assert [item["paper_id"] for item in library.json()["items"]] == [paper_id]
    assert reader.status_code == 200
    assert reader.json()["pdf_state"] == "available"
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content == PDF_BYTES

    metadata = client.patch(
        f"/papers/{paper_id}/metadata",
        json={
            "changes": {"title": "Explicitly enriched title"},
            "expected_revision": reader.json()["metadata_revision"],
        },
    )
    assert metadata.status_code == 200
    assert metadata.json()["metadata"]["title"] == "Explicitly enriched title"
    assert read_index_snapshot(index_csv).iloc[0]["tags"] == ""


def test_import_reports_partial_failure_missing_file_and_repeated_import_without_corrupting_existing_records(tmp_path: Path) -> None:
    workspace, papers_dir, notes_dir, index_csv = _workspace(tmp_path)
    (papers_dir / "Good.pdf").write_bytes(PDF_BYTES)
    (papers_dir / "Invalid.pdf").write_bytes(b"not a PDF")
    client = _client(workspace, papers_dir, notes_dir, index_csv)

    scan = client.post("/papers/scan", json={}).json()
    statuses = {item["relative_path"]: item["status"] for item in scan["candidates"]}
    assert statuses == {"Good.pdf": "new", "Invalid.pdf": "invalid"}
    partial = client.post(
        "/papers/import",
        json={"relative_paths": ["Good.pdf", "Invalid.pdf"]},
    )
    outcomes = {item["relative_path"]: item for item in partial.json()["results"]}
    assert partial.status_code == 200
    assert outcomes["Good.pdf"]["status"] == "imported"
    assert outcomes["Invalid.pdf"]["status"] == "invalid"
    assert len(read_index_snapshot(index_csv)) == 1

    repeated = client.post("/papers/import", json={"relative_paths": ["Good.pdf"]})
    assert repeated.status_code == 200
    assert repeated.json()["results"][0]["status"] == "already_registered"
    assert len(read_index_snapshot(index_csv)) == 1

    (papers_dir / "Gone.pdf").write_bytes(PDF_BYTES + b"gone")
    assert client.post("/papers/scan", json={}).status_code == 200
    (papers_dir / "Gone.pdf").unlink()
    missing = client.post("/papers/import", json={"relative_paths": ["Gone.pdf"]})
    assert missing.status_code == 200
    assert missing.json()["results"][0]["status"] == "missing"
    assert len(read_index_snapshot(index_csv)) == 1

    reloaded_service = PdfScanImportService(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    assert reloaded_service.scan()["candidates"][0]["status"] == "already_registered"


def test_unreadable_pdf_scan_remains_non_mutating_and_import_rejects_unsafe_paths(tmp_path: Path, monkeypatch) -> None:
    workspace, papers_dir, notes_dir, index_csv = _workspace(tmp_path)
    (papers_dir / "Unreadable.pdf").write_bytes(PDF_BYTES)
    client = _client(workspace, papers_dir, notes_dir, index_csv)

    def fail_fingerprint(_path):
        raise OSError("private filesystem failure")

    monkeypatch.setattr("services.pdf_scan_import.pdf_sha256_with_metadata", fail_fingerprint)
    unreadable = client.post("/papers/scan", json={})
    assert unreadable.status_code == 200
    assert unreadable.json()["candidates"][0]["status"] == "unavailable"
    assert not index_csv.exists()
    assert "private filesystem failure" not in unreadable.text

    invalid = client.post("/papers/import", json={"relative_paths": ["../outside.pdf"]})
    assert invalid.status_code == 422
    assert str(tmp_path) not in invalid.text


def test_exact_hash_reconnect_preserves_existing_paper_owned_state(tmp_path: Path) -> None:
    workspace, papers_dir, notes_dir, index_csv = _workspace(tmp_path)
    original = papers_dir / "Original.pdf"
    original.write_bytes(PDF_BYTES)
    client = _client(workspace, papers_dir, notes_dir, index_csv)
    imported = client.post("/papers/import", json={"relative_paths": ["Original.pdf"]}).json()
    paper_id = imported["results"][0]["paper_id"]

    # These files represent Paper-owned and linked state.  Reconnect must only
    # update the existing index row's managed-file identity fields.
    (notes_dir / f"{paper_id}.md").write_text("saved reading note", encoding="utf-8")
    blocks = workspace / "data" / "note_blocks" / f"{paper_id}.json"
    blocks.parent.mkdir(parents=True)
    blocks.write_text('[{"id":"block-1","paper_id":"' + paper_id + '"}]', encoding="utf-8")
    links = workspace / "data" / "projects" / "links.json"
    links.parent.mkdir(parents=True)
    links.write_text('[{"paper_id":"' + paper_id + '","project_id":"project-1"}]', encoding="utf-8")
    before_owned = {path: path.read_bytes() for path in (notes_dir / f"{paper_id}.md", blocks, links)}

    dataframe = read_index_snapshot(index_csv)
    dataframe.loc[dataframe["paper_id"] == paper_id, "title"] = "Curated title"
    dataframe.loc[dataframe["paper_id"] == paper_id, "tags"] = "methods, review"
    from storage.index_store import save_index
    save_index(dataframe, index_csv)
    original.unlink()
    (papers_dir / "moved").mkdir()
    moved = papers_dir / "moved" / "Renamed.pdf"
    moved.write_bytes(PDF_BYTES)

    scan = client.post("/papers/scan", json={})
    assert scan.status_code == 200
    candidate = scan.json()["candidates"][0]
    assert candidate["status"] == "reconnect_available"
    assert candidate["can_import"] is False
    assert candidate["can_reconnect"] is True
    assert candidate["reconnect_paper_id"] == paper_id

    reconnected = client.post("/papers/reconnect", json={"paper_id": paper_id, "relative_path": "moved/Renamed.pdf"})
    assert reconnected.status_code == 200
    assert reconnected.json()["status"] == "reconnected"
    row = read_index_snapshot(index_csv).iloc[0]
    assert row["paper_id"] == paper_id
    assert row["filename"] == "Renamed.pdf"
    assert row["title"] == "Curated title"
    assert row["tags"] == "methods, review"
    assert all(path.read_bytes() == expected for path, expected in before_owned.items())
    assert str(workspace) not in reconnected.text


def test_exact_hash_reconnect_rejects_ambiguous_or_stale_candidates_without_mutation(tmp_path: Path) -> None:
    workspace, papers_dir, notes_dir, index_csv = _workspace(tmp_path)
    (papers_dir / "One.pdf").write_bytes(PDF_BYTES)
    (papers_dir / "Two.pdf").write_bytes(PDF_BYTES + b"two")
    client = _client(workspace, papers_dir, notes_dir, index_csv)
    first = client.post("/papers/import", json={"relative_paths": ["One.pdf"]}).json()["results"][0]["paper_id"]
    second = client.post("/papers/import", json={"relative_paths": ["Two.pdf"]}).json()["results"][0]["paper_id"]
    dataframe = read_index_snapshot(index_csv)
    dataframe.loc[dataframe["paper_id"] == second, "pdf_sha256"] = dataframe.loc[dataframe["paper_id"] == first, "pdf_sha256"].iloc[0]
    from storage.index_store import save_index
    save_index(dataframe, index_csv)
    (papers_dir / "One.pdf").unlink()
    (papers_dir / "Two.pdf").unlink()
    (papers_dir / "Moved.pdf").write_bytes(PDF_BYTES)

    scan = client.post("/papers/scan", json={}).json()
    assert scan["candidates"][0]["status"] == "reconnect_ambiguous"
    before = index_csv.read_bytes()
    conflict = client.post("/papers/reconnect", json={"paper_id": first, "relative_path": "Moved.pdf"})
    assert conflict.status_code == 409
    assert index_csv.read_bytes() == before
