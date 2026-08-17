from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from ingest.crossref import CrossrefLookupError
from ingest.pdf_inspector_adapter import StructuredPdfExtraction, StructuredPdfPage
from ingest.text_extractor import FullTextExtractionResult
from services.metadata_enrichment import MetadataEnrichmentService
from storage.extracted_text_store import (
    build_extraction_metadata,
    save_extracted_text,
    save_extraction_metadata,
)
from storage.index_store import INDEX_COLUMNS, save_index


PROFILE_TEXT = """Canonical Evidence Title
Jane Doe, John Smith
Abstract
Canonical local evidence supplies this abstract.
Keywords
canonical; evidence
Introduction
Body text.
"""


ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <published>2017-06-12T17:57:34Z</published>
    <title>Canonical arXiv Candidate</title>
    <summary>Canonical arXiv abstract.</summary>
    <author><name>Archive Author</name></author>
  </entry>
</feed>
"""


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    index_csv = tmp_path / "data" / "paper_index.csv"
    papers_dir = tmp_path / "papers"
    cache_dir = tmp_path / "data" / "extracted_text"
    papers_dir.mkdir(parents=True)
    pdf_path = papers_dir / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ncanonical fixture")
    record = {column: "" for column in INDEX_COLUMNS}
    record.update({
        "paper_id": "paper-1",
        "filename": pdf_path.name,
        "filepath": str(pdf_path),
        "status": "unread",
        "reading_priority": "normal",
        "is_archived": "false",
    })
    save_index(pd.DataFrame([record]), index_csv)
    return index_csv, papers_dir, cache_dir, pdf_path


def _save_pdf_inspector_cache(cache_dir: Path, pdf_path: Path, text: str) -> None:
    structured = StructuredPdfExtraction(
        status="success",
        classification="text",
        page_count=1,
        pages=[StructuredPdfPage(page_number=1, state="success", markdown=text)],
        text=text,
        markdown=text,
        provider_version="0.2.6",
    )
    result = FullTextExtractionResult(
        text=text,
        source="pdf-inspector",
        char_count=len(text),
        status="success",
        attempted_methods=["pdf-inspector"],
        structured_extraction=structured,
        provider="pdf-inspector",
        provider_version="0.2.6",
        content_format="markdown",
    )
    save_extracted_text("paper-1", text, cache_dir)
    metadata = build_extraction_metadata("paper-1", str(pdf_path), result, cache_dir)
    save_extraction_metadata("paper-1", metadata, cache_dir)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _fields(service: MetadataEnrichmentService) -> dict[str, object]:
    return {field.field: field for field in service.preview("paper-1").fields}


def test_current_canonical_cache_drives_doi_crossref_without_preview_extraction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    index_csv, papers_dir, cache_dir, pdf_path = _workspace(tmp_path)
    _save_pdf_inspector_cache(cache_dir, pdf_path, "DOI: 10.2000/canonical-cache")
    calls: list[str] = []
    monkeypatch.setattr(
        "services.metadata_enrichment.extract_full_text_from_pdf",
        lambda _path: (_ for _ in ()).throw(AssertionError("current cache must be reused")),
    )
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=cache_dir,
        crossref_lookup=lambda doi: calls.append(doi) or {
            "title": "Crossref Canonical Title",
            "doi": doi,
        },
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )
    before = (index_csv.read_bytes(), _tree_bytes(cache_dir))

    preview = service.preview("paper-1")
    fields = {field.field: field for field in preview.fields}

    assert calls == ["10.2000/canonical-cache"]
    assert fields["title"].candidate_value == "Crossref Canonical Title"
    assert fields["title"].source == "Crossref"
    assert fields["doi"].source == "Crossref"
    assert "Used the current canonical PDF extraction cache" in " ".join(preview.diagnostics)
    assert (index_csv.read_bytes(), _tree_bytes(cache_dir)) == before


def test_cached_pdf_doi_keeps_pdf_inspector_provenance_when_crossref_is_unavailable(
    tmp_path: Path,
) -> None:
    index_csv, papers_dir, cache_dir, pdf_path = _workspace(tmp_path)
    _save_pdf_inspector_cache(cache_dir, pdf_path, "DOI: 10.2000/local-only")
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=cache_dir,
        crossref_lookup=lambda _doi: (_ for _ in ()).throw(
            CrossrefLookupError("offline", error_type="network")
        ),
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )

    fields = _fields(service)

    assert fields["doi"].candidate_value == "10.2000/local-only"
    assert fields["doi"].source == "PDF-derived DOI · pdf-inspector"


def test_canonical_cache_text_drives_arxiv_detection_and_lookup(tmp_path: Path, monkeypatch) -> None:
    index_csv, papers_dir, cache_dir, pdf_path = _workspace(tmp_path)
    _save_pdf_inspector_cache(cache_dir, pdf_path, "Preprint\narXiv:1706.03762v7")
    requests: list[str] = []
    monkeypatch.setattr(
        "services.metadata_enrichment.extract_full_text_from_pdf",
        lambda _path: (_ for _ in ()).throw(AssertionError("current cache must be reused")),
    )

    def arxiv_get(url, headers, timeout):
        requests.append(url)
        return SimpleNamespace(status_code=200, text=ARXIV_ATOM)

    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=cache_dir,
        crossref_lookup=lambda _doi: {},
        arxiv_request_get=arxiv_get,
    )

    fields = _fields(service)

    assert len(requests) == 1
    assert "id_list=1706.03762" in requests[0]
    assert fields["title"].candidate_value == "Canonical arXiv Candidate"
    assert fields["title"].source == "arXiv"
    assert fields["authors"].source == "arXiv"


def test_canonical_cache_text_feeds_pdf_profile_with_provider_provenance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    index_csv, papers_dir, cache_dir, pdf_path = _workspace(tmp_path)
    _save_pdf_inspector_cache(cache_dir, pdf_path, PROFILE_TEXT)
    monkeypatch.setattr(
        "services.metadata_enrichment.extract_full_text_from_pdf",
        lambda _path: (_ for _ in ()).throw(AssertionError("current cache must be reused")),
    )
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=cache_dir,
        crossref_lookup=lambda _doi: {},
    )

    fields = _fields(service)

    assert fields["title"].candidate_value == "Canonical Evidence Title"
    assert fields["authors"].candidate_value == "Jane Doe, John Smith"
    assert fields["abstract"].candidate_value.startswith("Canonical local evidence")
    assert fields["keywords"].candidate_value == "canonical, evidence"
    assert fields["title"].source == "PDF-derived profile · pdf-inspector"
    assert fields["abstract"].source == "PDF-derived profile · pdf-inspector"


def test_cache_absent_preview_extracts_once_and_persists_nothing(tmp_path: Path, monkeypatch) -> None:
    index_csv, papers_dir, cache_dir, _pdf_path = _workspace(tmp_path)
    calls: list[Path] = []
    preview_text = "DOI: 10.2000/preview-only\n" + PROFILE_TEXT

    def preview_extract(path: Path) -> FullTextExtractionResult:
        calls.append(path)
        return FullTextExtractionResult(
            text=preview_text,
            source="pdf-inspector",
            provider="pdf-inspector",
            provider_version="0.2.6",
            content_format="markdown",
            char_count=len(preview_text),
            status="success",
            attempted_methods=["pdf-inspector"],
        )

    monkeypatch.setattr("services.metadata_enrichment.extract_full_text_from_pdf", preview_extract)
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=cache_dir,
        crossref_lookup=lambda _doi: {},
    )
    before = index_csv.read_bytes()

    preview = service.preview("paper-1")
    fields = {field.field: field for field in preview.fields}

    assert len(calls) == 1
    assert fields["doi"].candidate_value == "10.2000/preview-only"
    assert fields["doi"].source == "PDF-derived DOI · pdf-inspector"
    assert fields["authors"].source == "PDF-derived profile · pdf-inspector"
    assert "without persisting an extraction cache" in " ".join(preview.diagnostics)
    assert index_csv.read_bytes() == before
    assert _tree_bytes(cache_dir) == {}


def test_stale_cache_is_not_reused_or_replaced_during_preview(tmp_path: Path, monkeypatch) -> None:
    index_csv, papers_dir, cache_dir, pdf_path = _workspace(tmp_path)
    _save_pdf_inspector_cache(cache_dir, pdf_path, "DOI: 10.2000/stale-cache")
    cached_before = _tree_bytes(cache_dir)
    pdf_path.write_bytes(b"%PDF-1.4\ncurrent replacement")
    calls: list[Path] = []

    def preview_extract(path: Path) -> FullTextExtractionResult:
        calls.append(path)
        text = "DOI: 10.2000/current-pdf"
        return FullTextExtractionResult(
            text=text,
            source="pdf-inspector",
            provider="pdf-inspector",
            char_count=len(text),
            status="success",
            attempted_methods=["pdf-inspector"],
        )

    monkeypatch.setattr("services.metadata_enrichment.extract_full_text_from_pdf", preview_extract)
    crossref_calls: list[str] = []
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=cache_dir,
        crossref_lookup=lambda doi: crossref_calls.append(doi) or {"doi": doi},
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )

    preview = service.preview("paper-1")

    assert len(calls) == 1
    assert crossref_calls == ["10.2000/current-pdf"]
    assert "stale" in " ".join(preview.diagnostics).casefold()
    assert _tree_bytes(cache_dir) == cached_before


def test_pdf_inspector_failure_uses_markitdown_for_metadata_preview(
    tmp_path: Path,
    monkeypatch,
) -> None:
    index_csv, papers_dir, cache_dir, _pdf_path = _workspace(tmp_path)

    class SuccessfulMarkItDown:
        def convert(self, path: str):
            return SimpleNamespace(text_content=PROFILE_TEXT)

    class UnexpectedPdfReader:
        def __init__(self, path: str) -> None:
            raise AssertionError("pypdf must not run after MarkItDown succeeds")

    monkeypatch.setattr(
        "ingest.text_extractor.extract_structured_pdf",
        lambda _path: StructuredPdfExtraction(
            status="failed",
            errors=["pdf-inspector: private failure"],
        ),
    )
    monkeypatch.setattr("ingest.text_extractor.MarkItDown", SuccessfulMarkItDown)
    monkeypatch.setattr("ingest.text_extractor.PdfReader", UnexpectedPdfReader)
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=cache_dir,
        crossref_lookup=lambda _doi: {},
    )

    fields = _fields(service)

    assert fields["title"].candidate_value == "Canonical Evidence Title"
    assert fields["title"].source == "PDF-derived profile · MarkItDown fallback"


def test_markitdown_failure_uses_pypdf_for_metadata_preview(tmp_path: Path, monkeypatch) -> None:
    index_csv, papers_dir, cache_dir, _pdf_path = _workspace(tmp_path)

    class FailingMarkItDown:
        def convert(self, path: str):
            raise RuntimeError("private MarkItDown failure")

    class FakePage:
        def extract_text(self) -> str:
            return PROFILE_TEXT

    class SuccessfulPdfReader:
        def __init__(self, path: str) -> None:
            self.pages = [FakePage()]

    monkeypatch.setattr(
        "ingest.text_extractor.extract_structured_pdf",
        lambda _path: StructuredPdfExtraction(
            status="failed",
            errors=["pdf-inspector: private failure"],
        ),
    )
    monkeypatch.setattr("ingest.text_extractor.MarkItDown", FailingMarkItDown)
    monkeypatch.setattr("ingest.text_extractor.PdfReader", SuccessfulPdfReader)
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=cache_dir,
        crossref_lookup=lambda _doi: {},
    )

    preview = service.preview("paper-1")
    fields = {field.field: field for field in preview.fields}

    assert fields["title"].candidate_value == "Canonical Evidence Title"
    assert fields["title"].source == "PDF-derived profile · pypdf fallback"
    assert "private" not in " ".join(preview.diagnostics).casefold()
