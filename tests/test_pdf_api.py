from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import dependencies
from api.main import create_app
from api.pdf_files import ManagedPdfResult, ManagedPdfState, resolve_managed_pdf
from api.routes import PDF_INVALID_DETAIL, PDF_MISSING_DETAIL, PDF_UNAVAILABLE_DETAIL


PDF_BYTES = b"%PDF-1.4\n% disposable test PDF\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"


def write_index(index_csv: Path, records: list[dict[str, object]]) -> None:
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=["paper_id", "filename", "filepath"]).to_csv(index_csv, index=False)


def resolve_fixture(tmp_path: Path, record: dict[str, object] | None, paper_id: str = "paper-1") -> ManagedPdfResult:
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir(exist_ok=True)
    index_csv = tmp_path / "data" / "paper_index.csv"
    write_index(index_csv, [record] if record else [])
    return resolve_managed_pdf(paper_id, index_csv=index_csv, papers_dir=papers_dir)


def client_for(result: ManagedPdfResult) -> TestClient:
    application = create_app()
    application.dependency_overrides[dependencies.get_managed_pdf] = lambda: result
    return TestClient(application)


def test_valid_managed_pdf_streams_exact_bytes_inline_and_supports_ranges(tmp_path: Path) -> None:
    pdf_path = tmp_path / "papers" / "paper.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(PDF_BYTES)
    result = resolve_fixture(tmp_path, {"paper_id": "paper-1", "filename": "paper.pdf"})
    client = client_for(result)

    response = client.get("/papers/paper-1/pdf")
    ranged = client.get("/papers/paper-1/pdf", headers={"Range": "bytes=1-4"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["accept-ranges"] == "bytes"
    assert response.content == PDF_BYTES
    assert ranged.status_code == 206
    assert ranged.content == PDF_BYTES[1:5]
    assert ranged.headers["content-range"] == f"bytes 1-4/{len(PDF_BYTES)}"


def test_unknown_paper_id_is_distinct_and_private(tmp_path: Path) -> None:
    result = resolve_fixture(tmp_path, None, paper_id="unknown")
    response = client_for(result).get("/papers/unknown/pdf")

    assert result.state is ManagedPdfState.unknown_paper
    assert response.status_code == 404
    assert response.json() == {"detail": "Paper not found."}
    assert str(tmp_path) not in response.text


@pytest.mark.parametrize(
    "record",
    [
        {"paper_id": "paper-1", "filename": ""},
        {"paper_id": "paper-1", "filename": "missing.pdf"},
    ],
)
def test_missing_managed_pdf_returns_explicit_404(tmp_path: Path, record: dict[str, object]) -> None:
    result = resolve_fixture(tmp_path, record)
    response = client_for(result).get("/papers/paper-1/pdf")

    assert result.state is ManagedPdfState.missing
    assert response.status_code == 404
    assert response.json() == {"detail": PDF_MISSING_DETAIL}


def test_non_pdf_path_is_rejected_without_exposing_it(tmp_path: Path) -> None:
    text_path = tmp_path / "papers" / "private-record.txt"
    text_path.parent.mkdir()
    text_path.write_text("not a pdf", encoding="utf-8")
    result = resolve_fixture(tmp_path, {"paper_id": "paper-1", "filename": text_path.name})
    response = client_for(result).get("/papers/paper-1/pdf")

    assert result.state is ManagedPdfState.invalid
    assert response.status_code == 409
    assert response.json() == {"detail": PDF_INVALID_DETAIL}
    assert str(text_path) not in response.text


def test_pdf_named_directory_is_rejected_as_non_file(tmp_path: Path) -> None:
    directory = tmp_path / "papers" / "not-a-file.pdf"
    directory.mkdir(parents=True)
    result = resolve_fixture(tmp_path, {"paper_id": "paper-1", "filename": directory.name})
    response = client_for(result).get("/papers/paper-1/pdf")

    assert result.state is ManagedPdfState.invalid
    assert response.status_code == 409
    assert response.json() == {"detail": PDF_INVALID_DETAIL}
    assert str(directory) not in response.text


@pytest.mark.parametrize("indexed_path", ["../outside.pdf", "papers/../outside.pdf"])
def test_traversal_outside_managed_root_is_rejected(tmp_path: Path, indexed_path: str) -> None:
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(PDF_BYTES)
    result = resolve_fixture(tmp_path, {"paper_id": "paper-1", "filepath": indexed_path, "filename": "paper.pdf"})
    response = client_for(result).get("/papers/paper-1/pdf")

    assert result.state is ManagedPdfState.invalid
    assert response.status_code == 409
    assert response.json() == {"detail": PDF_INVALID_DETAIL}
    assert str(outside) not in response.text


def test_absolute_path_outside_managed_root_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside" / "private.pdf"
    outside.parent.mkdir()
    outside.write_bytes(PDF_BYTES)
    result = resolve_fixture(tmp_path, {"paper_id": "paper-1", "filepath": str(outside), "filename": outside.name})

    response = client_for(result).get("/papers/paper-1/pdf")

    assert result.state is ManagedPdfState.invalid
    assert response.status_code == 409
    assert str(outside) not in response.text


def test_unavailable_file_returns_generic_503_without_path() -> None:
    private_path = Path("C:/private/library/secret.pdf")
    result = ManagedPdfResult(ManagedPdfState.unavailable, path=private_path)
    response = client_for(result).get("/papers/paper-1/pdf")

    assert response.status_code == 503
    assert response.json() == {"detail": PDF_UNAVAILABLE_DETAIL}
    assert str(private_path) not in response.text


def test_pdf_route_preserves_existing_get_only_api_surface() -> None:
    application = create_app()
    paths = application.openapi()["paths"]

    existing = {"/health", "/library/status", "/papers", "/papers/{paper_id}"}
    assert existing <= set(paths)
    assert set(paths) == {*existing, "/papers/{paper_id}/pdf"}
    assert all(set(operations) == {"get"} for operations in paths.values())
    assert not any(
        {"POST", "PUT", "PATCH", "DELETE"} & (getattr(route, "methods", None) or set())
        for route in application.routes
    )
