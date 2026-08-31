from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import dependencies
from api.adapters import PaperContractError, adapt_reader_snapshot
from api.main import UNAVAILABLE_DETAIL, create_app
from api.schemas import ReaderSnapshotResponse
from services.paper_metadata_mutation import paper_metadata_revision, paper_tags_revision


def reader_snapshot(
    *,
    paper_id: str = "paper-1",
    note: str = "# Saved note\n\nExact whitespace stays.\n",
    missing_pdf: bool = False,
    warnings: list[str] | None = None,
) -> dict[str, object]:
    note_bytes = note.encode("utf-8")
    editable_metadata = {
        "title": "Reader Snapshot Paper",
        "authors": "Example Author",
        "year": "2026",
        "journal": "Journal of Read-only Contracts",
        "doi": "",
        "abstract": "Stored abstract.",
        "keywords": "snapshot",
    }
    return {
        "paper": {
            "paper_id": paper_id,
            "title": "Reader Snapshot Paper",
            "first_author": "Example Author",
            "year": "2026",
            "status": "reading",
            "priority": "normal",
            "tags": ["reader"],
            "archived": False,
            "missing_pdf": missing_pdf,
            "health": ["missing_pdf"] if missing_pdf else [],
            "authors": ["Example Author"],
            "journal": "Journal of Read-only Contracts",
            "abstract": "Stored abstract.",
            "keywords": ["snapshot"],
            "arxiv_id": "",
            "filename": "paper-1.pdf",
            "relative_pdf_path": "" if missing_pdf else "papers/paper-1.pdf",
            "doi": "",
            "project_links": [],
            "note_available": bool(note),
            "extracted_text_available": False,
            "profile_available": False,
            "lifecycle_state": "active",
            "recoverable_warnings": ["missing_pdf"] if missing_pdf else [],
            "reading_status_revision": "a" * 64,
            "pdf_revision": "b" * 64,
            "lifecycle_revision": "c" * 64,
            "filepath": "private/storage/value.pdf",
        },
        "editable_metadata": editable_metadata,
        "metadata_revision": paper_metadata_revision(editable_metadata),
        "tags_revision": paper_tags_revision({"tags": "reader"}),
        "pdf_state": "missing" if missing_pdf else "available",
        "saved_note_available": bool(note),
        "saved_note_content": note,
        "canonical_note_header": {
            "template_version": "1.0",
            "paper_id": paper_id,
            "title": "Reader Snapshot Paper",
            "doi": "",
            "arxiv_id": "",
            "year": "2026",
            "first_author": "Example Author",
            "tags": "reader",
            "internal_note_path": "private/storage/value.md",
        },
        "saved_note_baseline": {
            "exists": bool(note),
            "sha256": hashlib.sha256(note_bytes).hexdigest(),
            "size_bytes": len(note_bytes),
            "internal_revision": "not-public",
        },
        "warnings": list(warnings or []),
        "unavailable_reason": "PDF file is missing." if missing_pdf else "",
        "private_storage_root": "private/storage",
    }


def client_for(snapshot: dict[str, object] | None) -> TestClient:
    application = create_app()

    def snapshot_provider(paper_id: str):
        return deepcopy(snapshot)

    application.dependency_overrides[dependencies.get_reader_snapshot] = snapshot_provider
    return TestClient(application)


def test_reader_snapshot_returns_exact_saved_note_and_allowlisted_nested_fields() -> None:
    note = "  first line\r\n\r\n<script>alert('text only')</script>\nlast line  "
    response = client_for(reader_snapshot(note=note)).get("/papers/paper-1/reader")

    assert response.status_code == 200
    body = response.json()
    assert body["saved_note_content"] == note
    assert set(body) == set(ReaderSnapshotResponse.model_fields)
    assert set(body["canonical_note_header"]) == {
        "template_version",
        "paper_id",
        "title",
        "doi",
        "arxiv_id",
        "year",
        "first_author",
        "tags",
    }
    assert set(body["saved_note_baseline"]) == {"exists", "sha256", "size_bytes"}
    assert "filepath" not in body["paper"]
    assert "private" not in response.text


def test_reader_snapshot_missing_note_is_a_successful_empty_read_state() -> None:
    response = client_for(reader_snapshot(note="")).get("/papers/paper-1/reader")

    assert response.status_code == 200
    assert response.json()["saved_note_available"] is False
    assert response.json()["saved_note_content"] == ""
    assert response.json()["saved_note_baseline"] == {
        "exists": False,
        "sha256": hashlib.sha256(b"").hexdigest(),
        "size_bytes": 0,
    }


def test_reader_snapshot_missing_pdf_and_present_note_are_independent_success_states() -> None:
    response = client_for(reader_snapshot(note="Persisted note", missing_pdf=True)).get(
        "/papers/paper-1/reader"
    )

    assert response.status_code == 200
    assert response.json()["pdf_state"] == "missing"
    assert response.json()["paper"]["missing_pdf"] is True
    assert response.json()["saved_note_available"] is True
    assert response.json()["saved_note_content"] == "Persisted note"


def test_reader_snapshot_unreadable_note_warning_remains_a_successful_read_state() -> None:
    snapshot = reader_snapshot(note="", warnings=["saved_note_unavailable"])
    response = client_for(snapshot).get("/papers/paper-1/reader")

    assert response.status_code == 200
    assert response.json()["warnings"] == ["saved_note_unavailable"]
    assert response.json()["saved_note_available"] is False


def test_unknown_reader_paper_returns_generic_404() -> None:
    response = client_for(None).get("/papers/unknown/reader")

    assert response.status_code == 404
    assert response.json() == {"detail": "Paper not found."}


def test_reader_dependency_calls_only_snapshot_builder_once(monkeypatch) -> None:
    calls: list[str] = []

    def build(paper_id: str):
        calls.append(paper_id)
        return reader_snapshot(paper_id=paper_id)

    monkeypatch.setattr(dependencies.library_read_model, "build_reader_snapshot", build)
    response = TestClient(create_app()).get("/papers/paper-1/reader")

    assert response.status_code == 200
    assert calls == ["paper-1"]


def test_reader_builder_failure_is_generic_503_without_private_details(monkeypatch) -> None:
    def fail(_paper_id: str):
        raise OSError("private/storage/notes/paper-1.md could not be read")

    monkeypatch.setattr(dependencies.library_read_model, "build_reader_snapshot", fail)
    response = TestClient(create_app()).get("/papers/paper-1/reader")

    assert response.status_code == 503
    assert response.json() == {"detail": UNAVAILABLE_DETAIL}
    assert "private/storage" not in response.text


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"paper": "not-an-object"}),
        lambda value: value.update({"canonical_note_header": []}),
        lambda value: value.update({"saved_note_baseline": []}),
        lambda value: value.update({"saved_note_available": "true"}),
        lambda value: value.update({"saved_note_content": None}),
        lambda value: value.update({"warnings": "saved_note_unavailable"}),
        lambda value: value["saved_note_baseline"].update({"size_bytes": "12"}),
    ],
)
def test_malformed_reader_snapshot_is_rejected_as_generic_503(mutate) -> None:
    snapshot = reader_snapshot()
    mutate(snapshot)

    response = client_for(snapshot).get("/papers/paper-1/reader")

    assert response.status_code == 503
    assert response.json() == {"detail": UNAVAILABLE_DETAIL}


@pytest.mark.parametrize("pdf_state", ["ready", "unavailable", "", "AVAILABLE"])
def test_unknown_reader_pdf_state_is_rejected(pdf_state: str) -> None:
    snapshot = reader_snapshot()
    snapshot["pdf_state"] = pdf_state

    with pytest.raises(PaperContractError):
        adapt_reader_snapshot(snapshot)


def test_reader_snapshot_rejects_pdf_state_that_conflicts_with_paper() -> None:
    snapshot = reader_snapshot()
    snapshot["pdf_state"] = "missing"

    with pytest.raises(PaperContractError):
        adapt_reader_snapshot(snapshot)


def test_reader_response_models_forbid_unknown_nested_fields() -> None:
    public = adapt_reader_snapshot(reader_snapshot()).model_dump()
    public["canonical_note_header"]["unexpected"] = "value"

    with pytest.raises(ValidationError):
        ReaderSnapshotResponse.model_validate(public)


def test_openapi_documents_reader_snapshot_as_get_only() -> None:
    schema = create_app().openapi()
    operation = schema["paths"]["/papers/{paper_id}/reader"]["get"]

    assert set(schema["paths"]["/papers/{paper_id}/reader"]) == {"get"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ReaderSnapshotResponse"
    )
    response_schema = schema["components"]["schemas"]["ReaderSnapshotResponse"]
    assert set(response_schema["required"]) == set(ReaderSnapshotResponse.model_fields)
