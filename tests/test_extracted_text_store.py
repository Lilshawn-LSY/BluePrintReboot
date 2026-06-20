from ingest.text_extractor import FullTextExtractionResult
from storage.extracted_text_store import (
    build_extraction_metadata,
    clear_extraction_cache,
    extracted_text_path,
    extraction_cache_status,
    extraction_metadata_path,
    has_reusable_extracted_text_cache,
    is_extraction_cache_stale,
    load_cached_extracted_text,
    load_extraction_metadata,
    save_extracted_text,
    save_extraction_metadata,
)
from tests.helpers import make_workspace


CACHE_STATUS_CORE_KEYS = {
    "has_text_file",
    "has_metadata_file",
    "has_reusable_text_cache",
    "is_stale",
    "pdf_sha256",
    "cached_pdf_sha256",
    "status",
    "char_count",
    "error",
    "source",
}


def assert_stable_cache_status_schema(status: dict) -> None:
    assert CACHE_STATUS_CORE_KEYS <= set(status)


def test_extracted_text_and_metadata_paths_are_paper_id_based() -> None:
    cache_dir = make_workspace("text-cache-paths")

    assert extracted_text_path("paper-1", cache_dir) == cache_dir / "paper-1.txt"
    assert extraction_metadata_path("paper-1", cache_dir) == cache_dir / "paper-1.json"


def test_save_and_load_cached_extracted_text() -> None:
    cache_dir = make_workspace("text-cache-save")

    save_extracted_text("paper-1", "full text", cache_dir)

    assert load_cached_extracted_text("paper-1", cache_dir) == "full text"


def test_save_and_load_extraction_metadata() -> None:
    cache_dir = make_workspace("text-cache-metadata")
    result = FullTextExtractionResult(
        text="abc",
        source="pypdf",
        char_count=3,
        errors=[],
        status="success",
        attempted_methods=["pypdf"],
    )
    metadata = build_extraction_metadata("paper-1", "paper.pdf", result, cache_dir)

    save_extraction_metadata("paper-1", metadata, cache_dir)
    loaded = load_extraction_metadata("paper-1", cache_dir)

    assert loaded["paper_id"] == "paper-1"
    assert loaded["source"] == "pypdf"
    assert loaded["char_count"] == 3
    assert loaded["status"] == "success"
    assert loaded["pdf_size_bytes"] == 0
    assert loaded["pdf_modified_at"] == ""
    assert loaded["pdf_sha256"] == ""


def test_extraction_cache_status_and_clear() -> None:
    cache_dir = make_workspace("text-cache-status")
    save_extracted_text("paper-1", "full text", cache_dir)
    save_extraction_metadata(
        "paper-1",
        {
            "paper_id": "paper-1",
            "status": "success",
            "source": "pypdf",
            "char_count": 9,
            "extracted_at": "2026-06-15T00:00:00+00:00",
            "errors": [],
            "attempted_methods": ["pypdf"],
        },
        cache_dir,
    )

    status = extraction_cache_status("paper-1", cache_dir)
    assert_stable_cache_status_schema(status)
    assert status["has_text_file"] is True
    assert status["has_metadata_file"] is True
    assert status["has_reusable_text_cache"] is True
    assert status["is_stale"] is False
    assert status["pdf_sha256"] == ""
    assert status["cached_pdf_sha256"] == ""
    assert status["error"] == ""
    assert status["has_text"] is True
    assert status["has_metadata"] is True
    assert status["status"] == "success"
    assert status["source"] == "pypdf"

    clear_extraction_cache("paper-1", cache_dir)
    status = extraction_cache_status("paper-1", cache_dir)
    assert_stable_cache_status_schema(status)
    assert status["has_text_file"] is False
    assert status["has_metadata_file"] is False
    assert status["has_reusable_text_cache"] is False
    assert status["has_text"] is False
    assert status["has_metadata"] is False


def test_failed_empty_extraction_cache_is_not_reusable() -> None:
    cache_dir = make_workspace("text-cache-failed-empty")
    save_extracted_text("paper-1", "", cache_dir)
    save_extraction_metadata(
        "paper-1",
        {
            "paper_id": "paper-1",
            "status": "empty",
            "source": "none",
            "char_count": 0,
            "errors": ["No readable text extracted."],
        },
        cache_dir,
    )

    assert has_reusable_extracted_text_cache("paper-1", cache_dir) is False


def test_successful_non_empty_extraction_cache_is_reusable() -> None:
    cache_dir = make_workspace("text-cache-reusable")
    pdf_path = cache_dir / "paper.pdf"
    pdf_path.write_bytes(b"current PDF")
    save_extracted_text("paper-1", "usable text", cache_dir)
    save_extraction_metadata(
        "paper-1",
        {
            "paper_id": "paper-1",
            "status": "success",
            "source": "pypdf",
            "char_count": 11,
            "errors": [],
        },
        cache_dir,
    )

    status = extraction_cache_status("paper-1", cache_dir, pdf_path=pdf_path)

    assert_stable_cache_status_schema(status)
    assert status["is_stale"] is False
    assert status["pdf_sha256"]
    assert status["cached_pdf_sha256"] == ""
    assert has_reusable_extracted_text_cache("paper-1", cache_dir) is True
    assert is_extraction_cache_stale("paper-1", pdf_path, cache_dir) is False


def test_same_pdf_hash_is_not_stale() -> None:
    workspace = make_workspace("text-cache-same-pdf")
    cache_dir = workspace / "cache"
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"same PDF")
    result = FullTextExtractionResult(
        text="usable text",
        source="pypdf",
        char_count=11,
        errors=[],
        status="success",
        attempted_methods=["pypdf"],
    )
    save_extracted_text("paper-1", result.text, cache_dir)
    save_extraction_metadata(
        "paper-1",
        build_extraction_metadata("paper-1", str(pdf_path), result, cache_dir),
        cache_dir,
    )

    status_without_pdf = extraction_cache_status("paper-1", cache_dir)
    status = extraction_cache_status("paper-1", cache_dir, pdf_path=pdf_path)

    assert_stable_cache_status_schema(status_without_pdf)
    assert_stable_cache_status_schema(status)
    assert set(status_without_pdf) == set(status)
    assert is_extraction_cache_stale("paper-1", pdf_path, cache_dir) is False
    assert status["is_stale"] is False
    assert status["pdf_sha256"] == status["cached_pdf_sha256"]


def test_changed_pdf_hash_is_stale() -> None:
    workspace = make_workspace("text-cache-changed-pdf")
    cache_dir = workspace / "cache"
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"original PDF")
    result = FullTextExtractionResult(
        text="usable text",
        source="pypdf",
        char_count=11,
        errors=[],
        status="success",
        attempted_methods=["pypdf"],
    )
    save_extracted_text("paper-1", result.text, cache_dir)
    save_extraction_metadata(
        "paper-1",
        build_extraction_metadata("paper-1", str(pdf_path), result, cache_dir),
        cache_dir,
    )
    pdf_path.write_bytes(b"replacement PDF")

    status = extraction_cache_status("paper-1", cache_dir, pdf_path=pdf_path)

    assert_stable_cache_status_schema(status)
    assert is_extraction_cache_stale("paper-1", pdf_path, cache_dir) is True
    assert status["is_stale"] is True
    assert status["pdf_sha256"] != status["cached_pdf_sha256"]
