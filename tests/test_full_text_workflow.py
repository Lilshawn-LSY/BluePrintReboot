import pandas as pd

from ingest.text_extractor import FullTextExtractionResult
from services.full_text_workflow import clear_text_cache_for_paper, extract_text_for_paper
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


def test_successful_extraction_updates_cache_and_index(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-success")
    cache_dir = workspace / "cache"
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(workspace / "paper.pdf"),
        "title": "Paper",
    }
    (workspace / "paper.pdf").write_bytes(b"%PDF-1.4\n")
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
        "filepath": str(workspace / "missing.pdf"),
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
    assert extraction_metadata_path("paper-1", cache_dir).exists()
    assert status["has_reusable_text_cache"] is False
    assert load_index(index_csv).iloc[0]["text_status"] == "failed"


def test_force_false_reuses_successful_cache(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-reuse")
    cache_dir = workspace / "cache"
    record = {
        "paper_id": "paper-1",
        "filename": "paper.pdf",
        "filepath": str(workspace / "paper.pdf"),
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


def test_force_false_reextracts_stale_cache(monkeypatch) -> None:
    workspace = make_workspace("full-text-service-stale")
    cache_dir = workspace / "cache"
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"original PDF")
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
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"original PDF")
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
        "filepath": str(workspace / "paper.pdf"),
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
        "filepath": str(workspace / "paper.pdf"),
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
