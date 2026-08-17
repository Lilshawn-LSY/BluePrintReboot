from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from api import dependencies
from api.main import create_app
from ingest.pdf_inspector_adapter import StructuredPdfExtraction, StructuredPdfPage
from ingest.text_extractor import FullTextExtractionResult
from services.full_text_workflow import (
    FullTextDocument,
    FullTextService,
    FullTextServiceUnavailable,
    FullTextStatus,
)
from storage.index_store import save_index
from tests.helpers import make_workspace


def full_text_client(monkeypatch, result: FullTextExtractionResult | None = None):
    workspace = make_workspace("full-text-api")
    pdf_path = workspace / "papers" / "paper.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\nfixture")
    pdf_path = pdf_path.resolve()
    index_csv = workspace / "data" / "paper_index.csv"
    save_index(
        pd.DataFrame([
            {
                "paper_id": "paper-1",
                "filename": "paper.pdf",
                "filepath": str(pdf_path),
                "title": "Full Text Paper",
            }
        ]),
        index_csv,
    )
    service = FullTextService(index_csv=index_csv, cache_dir=workspace / "cache")
    application = create_app()
    application.dependency_overrides[dependencies.get_full_text_service] = lambda: service
    if result is not None:
        monkeypatch.setattr("services.full_text_workflow.extract_full_text_from_pdf", lambda path: result)
    return TestClient(application), service, pdf_path


def structured_result(*, mixed: bool = False) -> FullTextExtractionResult:
    pages = [
        StructuredPdfPage(page_number=1, state="success", markdown="# Page one"),
        StructuredPdfPage(
            page_number=2,
            state="ocr_needed" if mixed else "success",
            markdown="" if mixed else "Page two",
            ocr_needed=mixed,
        ),
    ]
    text = "# Page one" if mixed else "# Page one\n\nPage two"
    structured = StructuredPdfExtraction(
        status="ocr_needed" if mixed else "success",
        classification="mixed" if mixed else "text",
        page_count=2,
        pages=pages,
        text=text,
        markdown=text,
        ocr_needed_pages=[2] if mixed else [],
        provider_version="test-0.2.6",
    )
    return FullTextExtractionResult(
        text=text,
        source="pdf-inspector",
        provider="pdf-inspector",
        provider_version="test-0.2.6",
        content_format="markdown",
        char_count=len(text),
        status=structured.status,
        attempted_methods=["pdf-inspector"],
        structured_extraction=structured,
    )


def test_full_text_status_starts_not_extracted_and_extraction_is_explicit(monkeypatch) -> None:
    client, _service, _pdf_path = full_text_client(monkeypatch, structured_result())

    status = client.get("/papers/paper-1/full-text/status")
    extracted = client.post("/papers/paper-1/full-text/extract", json={"force": False})

    assert status.status_code == 200
    assert status.json()["state"] == "not_extracted"
    assert status.json()["can_extract"] is True
    assert extracted.status_code == 200
    assert extracted.json()["state"] == "cached"
    assert extracted.json()["content"] == "# Page one\n\nPage two"
    assert extracted.json()["provider"] == "pdf-inspector"
    assert extracted.json()["provider_version"] == "test-0.2.6"
    assert extracted.json()["content_format"] == "markdown"
    assert extracted.json()["page_count"] == 2
    assert extracted.json()["char_count"] == len("# Page one\n\nPage two")


def test_full_text_document_returns_cached_content_and_stale_state(monkeypatch) -> None:
    client, _service, pdf_path = full_text_client(monkeypatch, structured_result())
    assert client.post("/papers/paper-1/full-text/extract", json={"force": False}).status_code == 200

    cached = client.get("/papers/paper-1/full-text")
    pdf_path.write_bytes(b"%PDF-1.4\nreplacement")
    stale = client.get("/papers/paper-1/full-text")

    assert cached.json()["state"] == "cached"
    assert cached.json()["content"] == "# Page one\n\nPage two"
    assert stale.json()["state"] == "stale"
    assert stale.json()["is_stale"] is True
    assert stale.json()["has_content"] is True
    assert stale.json()["content"] == cached.json()["content"]


def test_mixed_extraction_exposes_content_and_ocr_needed_pages(monkeypatch) -> None:
    client, _service, _pdf_path = full_text_client(monkeypatch, structured_result(mixed=True))

    response = client.post("/papers/paper-1/full-text/extract", json={"force": False})

    assert response.status_code == 200
    assert response.json()["state"] == "ocr_needed"
    assert response.json()["classification"] == "mixed"
    assert response.json()["ocr_needed_pages"] == [2]
    assert response.json()["has_content"] is True
    assert response.json()["content"] == "# Page one"
    assert "failure" not in response.json()["message"].lower()


def test_scanned_extraction_is_ocr_needed_without_fabricated_content(monkeypatch) -> None:
    structured = StructuredPdfExtraction(
        status="ocr_needed",
        classification="scanned",
        page_count=2,
        pages=[
            StructuredPdfPage(page_number=1, state="ocr_needed", ocr_needed=True),
            StructuredPdfPage(page_number=2, state="ocr_needed", ocr_needed=True),
        ],
        ocr_needed_pages=[1, 2],
        provider_version="test-0.2.6",
    )
    result = FullTextExtractionResult(
        status="ocr_needed",
        provider="pdf-inspector",
        provider_version="test-0.2.6",
        attempted_methods=["pdf-inspector", "markitdown", "pypdf"],
        structured_extraction=structured,
    )
    client, _service, _pdf_path = full_text_client(monkeypatch, result)

    response = client.post("/papers/paper-1/full-text/extract", json={"force": False})

    assert response.status_code == 200
    assert response.json()["state"] == "ocr_needed"
    assert response.json()["classification"] == "scanned"
    assert response.json()["ocr_needed_pages"] == [1, 2]
    assert response.json()["has_content"] is False
    assert response.json()["content"] == ""
    assert "failure" not in response.json()["message"].lower()


def test_failed_extraction_returns_bounded_retryable_state(monkeypatch) -> None:
    failure = FullTextExtractionResult(
        status="failed",
        errors=["private/path/provider failure"],
        attempted_methods=["pdf-inspector", "markitdown", "pypdf"],
    )
    client, _service, _pdf_path = full_text_client(monkeypatch, failure)

    response = client.post("/papers/paper-1/full-text/extract", json={"force": True})

    assert response.status_code == 200
    assert response.json()["state"] == "failed"
    assert response.json()["has_content"] is False
    assert response.json()["can_extract"] is True
    assert response.json()["content"] == ""
    assert "private/path" not in response.text


def test_extraction_command_forwards_force_for_retry_and_reextract() -> None:
    calls: list[bool] = []
    status = FullTextStatus(
        paper_id="paper-1",
        state="cached",
        extraction_state="success",
        source="pypdf",
        provider="pypdf",
        provider_version="",
        content_format="plain_text",
        classification="unknown",
        page_count=0,
        char_count=4,
        ocr_needed_pages=[],
        extracted_at="2026-08-17T00:00:00+00:00",
        has_content=True,
        is_stale=False,
        can_extract=True,
        previous_cache_preserved=False,
        message="Reusable full text is available from the local cache.",
    )

    class CapturingService:
        def extract(self, paper_id: str, *, force: bool = False):
            calls.append(force)
            return FullTextDocument(status=status, content="text")

    application = create_app()
    application.dependency_overrides[dependencies.get_full_text_service] = CapturingService
    client = TestClient(application)

    assert client.post("/papers/paper-1/full-text/extract", json={"force": False}).status_code == 200
    assert client.post("/papers/paper-1/full-text/extract", json={"force": True}).status_code == 200
    assert calls == [False, True]


def test_full_text_routes_use_generic_not_found_and_unavailable_boundaries() -> None:
    class MissingService:
        def status(self, paper_id: str):
            return None

    application = create_app()
    application.dependency_overrides[dependencies.get_full_text_service] = MissingService
    missing = TestClient(application).get("/papers/unknown/full-text/status")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Paper not found."}

    class BrokenService:
        def status(self, paper_id: str):
            raise FullTextServiceUnavailable("private/cache/path")

    application = create_app()
    application.dependency_overrides[dependencies.get_full_text_service] = BrokenService
    unavailable = TestClient(application).get("/papers/paper-1/full-text/status")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "detail": "The full-text extraction state could not be read or updated safely."
    }
    assert "private/cache" not in unavailable.text


def test_openapi_documents_full_text_read_and_command_routes() -> None:
    schema = create_app().openapi()

    assert set(schema["paths"]["/papers/{paper_id}/full-text/status"]) == {"get"}
    assert set(schema["paths"]["/papers/{paper_id}/full-text"]) == {"get"}
    assert set(schema["paths"]["/papers/{paper_id}/full-text/extract"]) == {"post"}
