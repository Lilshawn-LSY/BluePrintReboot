import pandas as pd
import pytest

from ingest.pdf_inspector_adapter import StructuredPdfExtraction, StructuredPdfPage
from ingest.text_extractor import FullTextExtractionResult
from services.full_text_workflow import (
    FullTextTransactionError,
    clear_text_cache_for_paper,
    extract_text_for_paper,
)
from storage.extracted_text_store import (
    extraction_cache_status,
    extraction_metadata_path,
    extracted_text_path,
    load_extraction_metadata,
)
from storage.index_store import load_index, save_index
from tests.helpers import make_workspace


def make_index(workspace, record):
    index_csv = workspace / "data" / "paper_index.csv"
    save_index(pd.DataFrame([record]), index_csv)
    return index_csv


def write_managed_pdf(workspace, contents=b"%PDF-1.4\n"):
    pdf_path = workspace / "papers" / "paper.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(contents)
    return pdf_path.resolve()


def test_successful_extraction_updates_cache_and_index(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-success")
    cache_dir = workspace / "cache"
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(write_managed_pdf(workspace)),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    monkeypatch.setattr(
        "services.full_text_workflow.extract_full_text_from_pdf",
        lambda path: FullTextExtractionResult(
            text="extracted text",
            source="pypdf",
            char_count=14,
            errors=[],
            status="success",
            attempted_methods=["pypdf"],
        ),
    )

    result = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)

    assert result.skipped is False
    assert extracted_text_path("paper-1", cache_dir).read_text(encoding="utf-8") == "extracted text"
    metadata = load_extraction_metadata("paper-1", cache_dir)
    assert metadata["pdf_size_bytes"] > 0
    assert metadata["pdf_sha256"]
    assert metadata["provider"] == "none"
    assert metadata["content_format"] == "plain_text"
    row = load_index(index_csv).iloc[0]
    assert row["text_status"] == "success"
    assert row["text_source"] == "pypdf"
    assert row["text_char_count"] == "14"


def test_failed_extraction_saves_metadata_but_is_not_reusable(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-failed")
    cache_dir = workspace / "cache"
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(write_managed_pdf(workspace)),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    monkeypatch.setattr(
        "services.full_text_workflow.extract_full_text_from_pdf",
        lambda path: FullTextExtractionResult(
            text="",
            source="none",
            char_count=0,
            errors=["no text"],
            status="failed",
            attempted_methods=[],
        ),
    )

    result = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)
    status = extraction_cache_status("paper-1", cache_dir)

    assert result.status == "failed"
    assert result.extraction_state == "failed"
    assert result.cache_state == "failed"
    assert extraction_metadata_path("paper-1", cache_dir).exists()
    assert status["has_reusable_text_cache"] is False
    assert status["cache_state"] == "failed"
    assert load_index(index_csv).iloc[0]["text_status"] == "failed"


def test_force_false_reuses_successful_cache(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-reuse")
    cache_dir = workspace / "cache"
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(write_managed_pdf(workspace)),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    calls = {"count": 0}

    def fake_extract(path):
        calls["count"] += 1
        return FullTextExtractionResult(
            text="cached text",
            source="pypdf",
            char_count=11,
            errors=[],
            status="success",
            attempted_methods=["pypdf"],
        )

    monkeypatch.setattr("services.full_text_workflow.extract_full_text_from_pdf", fake_extract)

    first = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)
    second = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)

    assert first.skipped is False
    assert second.skipped is True
    assert calls["count"] == 1


def test_ocr_needed_cache_is_reused_deterministically_after_reload(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-ocr-needed-reuse")
    cache_dir = workspace / "cache"
    pdf_path = write_managed_pdf(workspace, b"scanned PDF")
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(pdf_path),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    calls = {"count": 0}
    structured = StructuredPdfExtraction(
        status="ocr_needed",
        classification="scanned",
        classification_confidence=0.95,
        page_count=1,
        pages=[StructuredPdfPage(page_number=1, state="ocr_needed", ocr_needed=True)],
        ocr_needed_pages=[1],
        provider_version="test-0.2.6",
    )

    def fake_extract(path):
        calls["count"] += 1
        return FullTextExtractionResult(
            text="",
            source="none",
            char_count=0,
            status="ocr_needed",
            attempted_methods=["pdf-inspector"],
            structured_extraction=structured,
        )

    monkeypatch.setattr("services.full_text_workflow.extract_full_text_from_pdf", fake_extract)

    first = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)
    second = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)
    status = extraction_cache_status("paper-1", cache_dir, pdf_path=pdf_path)

    assert first.status == "ocr_needed"
    assert first.error == ""
    assert second.skipped is True
    assert second.cache_state == "ocr_needed"
    assert calls["count"] == 1
    assert status["has_reusable_text_cache"] is False
    assert status["has_reusable_extraction_cache"] is True
    assert status["cache_state"] == "ocr_needed"
    assert status["classification"] == "scanned"
    assert status["ocr_needed_pages"] == [1]
    assert status["structured_extraction"]["pages"][0]["page_number"] == 1
    assert status["structured_extraction"]["source_pdf_sha256"] == status["cached_pdf_sha256"]
    assert status["structured_extraction"]["source_pdf_size_bytes"] == pdf_path.stat().st_size


def test_force_false_reextracts_stale_cache(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-stale")
    cache_dir = workspace / "cache"
    pdf_path = write_managed_pdf(workspace, b"original PDF")
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(pdf_path),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    calls = {"count": 0}

    def fake_extract(path):
        calls["count"] += 1
        text = f"text {calls['count']}"
        return FullTextExtractionResult(
            text=text,
            source="pypdf",
            char_count=len(text),
            errors=[],
            status="success",
            attempted_methods=["pypdf"],
        )

    monkeypatch.setattr("services.full_text_workflow.extract_full_text_from_pdf", fake_extract)

    first = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)
    pdf_path.write_bytes(b"replacement PDF")
    second = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)

    assert first.skipped is False
    assert second.skipped is False
    assert calls["count"] == 2
    assert extracted_text_path("paper-1", cache_dir).read_text(encoding="utf-8") == "text 2"


def test_failed_stale_reextraction_preserves_previous_good_cache(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-stale-failure")
    cache_dir = workspace / "cache"
    pdf_path = write_managed_pdf(workspace, b"original PDF")
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(pdf_path),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    calls = {"count": 0}

    def fake_extract(path):
        calls["count"] += 1
        if calls["count"] == 1:
            return FullTextExtractionResult(
                text="previous good text",
                source="pypdf",
                char_count=18,
                errors=[],
                status="success",
                attempted_methods=["pypdf"],
            )
        return FullTextExtractionResult(
            text="",
            source="none",
            char_count=0,
            errors=["replacement extraction failed"],
            status="failed",
            attempted_methods=["pypdf"],
        )

    monkeypatch.setattr("services.full_text_workflow.extract_full_text_from_pdf", fake_extract)

    extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)
    original_metadata = load_extraction_metadata("paper-1", cache_dir)
    pdf_path.write_bytes(b"replacement PDF")
    result = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)
    status = extraction_cache_status("paper-1", cache_dir, pdf_path=pdf_path)
    preserved_metadata = load_extraction_metadata("paper-1", cache_dir)

    assert calls["count"] == 2
    assert extracted_text_path("paper-1", cache_dir).read_text(encoding="utf-8") == "previous good text"
    assert result.status == "failed"
    assert result.previous_cache_preserved is True
    assert result.recovery_failed is True
    assert result.error == "replacement extraction failed"
    assert status["has_reusable_text_cache"] is True
    assert status["is_stale"] is True
    assert status["previous_cache_preserved"] is True
    assert status["recovery_failed"] is True
    assert status["error"] == "replacement extraction failed"
    assert preserved_metadata["status"] == "success"
    assert preserved_metadata["pdf_sha256"] == original_metadata["pdf_sha256"]
    assert preserved_metadata["recovery_pdf_sha256"] == status["pdf_sha256"]
    assert load_index(index_csv).iloc[0]["text_status"] == "recovery_failed"


def test_force_true_bypasses_reusable_cache(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-force")
    cache_dir = workspace / "cache"
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(write_managed_pdf(workspace)),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    calls = {"count": 0}

    def fake_extract(path):
        calls["count"] += 1
        return FullTextExtractionResult(
            text=f"text {calls['count']}",
            source="pypdf",
            char_count=6,
            errors=[],
            status="success",
            attempted_methods=["pypdf"],
        )

    monkeypatch.setattr("services.full_text_workflow.extract_full_text_from_pdf", fake_extract)

    extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)
    extract_text_for_paper(record, force=True, cache_dir=cache_dir, index_csv=index_csv)

    assert calls["count"] == 2


def test_clear_text_cache_for_paper_removes_files_and_resets_index(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-clear")
    cache_dir = workspace / "cache"
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(write_managed_pdf(workspace)),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    monkeypatch.setattr(
        "services.full_text_workflow.extract_full_text_from_pdf",
        lambda path: FullTextExtractionResult(
            text="text",
            source="pypdf",
            char_count=4,
            errors=[],
            status="success",
            attempted_methods=["pypdf"],
        ),
    )
    extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)

    clear_text_cache_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)

    assert not extracted_text_path("paper-1", cache_dir).exists()
    assert not extraction_metadata_path("paper-1", cache_dir).exists()
    row = load_index(index_csv).iloc[0]
    assert row["text_status"] == ""
    assert row["text_source"] == ""
    assert row["text_char_count"] == ""
    assert row["text_extracted_at"] == ""


def test_index_failure_rolls_back_new_cache_and_does_not_report_success(monkeypatch) -> None:
    workspace = make_workspace("full-text-index-rollback")
    cache_dir = workspace / "data" / "extracted_text"
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(write_managed_pdf(workspace)),
        "title": "Paper",
    }
    index_csv = make_index(workspace, record)
    monkeypatch.setattr(
        "services.full_text_workflow.extract_full_text_from_pdf",
        lambda path: FullTextExtractionResult(
            text="new extracted text",
            source="pypdf",
            char_count=18,
            errors=[],
            status="success",
            attempted_methods=["pypdf"],
        ),
    )
    monkeypatch.setattr(
        "services.full_text_workflow.update_paper_metadata",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("forced index failure")),
    )

    with pytest.raises(FullTextTransactionError, match="rolled back"):
        extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)

    assert not extracted_text_path("paper-1", cache_dir).exists()
    assert not extraction_metadata_path("paper-1", cache_dir).exists()
    assert load_index(index_csv).iloc[0]["text_status"] == ""


def test_legacy_filename_only_row_uses_managed_papers_fallback(monkeypatch) -> None:
    workspace = make_workspace("full-text-filename-fallback")
    cache_dir = workspace / "data" / "extracted_text"
    pdf_path = write_managed_pdf(workspace)
    record = {
        "paper_id": "paper-1",
        "filename": pdf_path.name,
        "filepath": "",
        "title": "Legacy Paper",
    }
    index_csv = make_index(workspace, record)
    observed: list[object] = []

    def extract(path):
        observed.append(path)
        return FullTextExtractionResult(
            text="legacy text",
            source="pypdf",
            char_count=11,
            errors=[],
            status="success",
            attempted_methods=["pypdf"],
        )

    monkeypatch.setattr("services.full_text_workflow.extract_full_text_from_pdf", extract)
    result = extract_text_for_paper(record, cache_dir=cache_dir, index_csv=index_csv)

    assert result.status == "success"
    assert observed == [pdf_path]
