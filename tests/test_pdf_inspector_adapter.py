from __future__ import annotations

from types import SimpleNamespace

import pytest

from ingest.pdf_inspector_adapter import (
    StructuredPdfExtraction,
    StructuredPdfPage,
    canonical_full_text_projection,
    extract_structured_pdf,
)
from ingest.text_extractor import extract_full_text_from_pdf


def value(**kwargs):
    return SimpleNamespace(**kwargs)


class FakeInspector:
    __version__ = "test-0.2.6"

    def __init__(
        self,
        *,
        pdf_type: str,
        page_markdown: list[str],
        ocr_pages: list[int],
    ) -> None:
        self.pdf_type = pdf_type
        self.page_markdown = page_markdown
        self.ocr_pages = ocr_pages

    def process_pdf(self, path: str):
        return value(
            pdf_type=self.pdf_type,
            confidence=0.91,
            page_count=len(self.page_markdown),
            markdown="\n\n".join(text for text in self.page_markdown if text),
            pages_needing_ocr=self.ocr_pages,
            ocr_reasons_by_page=[
                value(page=page_number, reasons=["no_text_operators"])
                for page_number in self.ocr_pages
            ],
        )

    def extract_pages_markdown(self, path: str):
        return value(
            pages=[
                value(
                    page=index,
                    markdown=markdown,
                    needs_ocr=index + 1 in self.ocr_pages,
                    ocr_reason="no_text_operators" if index + 1 in self.ocr_pages else None,
                )
                for index, markdown in enumerate(self.page_markdown)
            ],
            pages_needing_ocr=self.ocr_pages,
        )

    def extract_text_with_positions(self, path: str):
        return [
            value(
                page=index + 1,
                text=markdown,
                x=12.0,
                y=24.0,
                width=120.0,
                height=14.0,
                font="Body",
                font_size=11.0,
                is_bold=False,
                is_italic=False,
                item_type="text",
            )
            for index, markdown in enumerate(self.page_markdown)
            if markdown
        ]


@pytest.mark.parametrize(
    ("upstream_type", "classification"),
    [
        ("text_based", "text"),
        ("scanned", "scanned"),
        ("image_based", "image-based"),
    ],
)
def test_normalizes_document_classification(upstream_type: str, classification: str) -> None:
    ocr_pages = [] if upstream_type == "text_based" else [1, 2]
    markdown = ["Page one", "Page two"] if upstream_type == "text_based" else ["", ""]

    result = extract_structured_pdf(
        "fixture.pdf",
        inspector=FakeInspector(pdf_type=upstream_type, page_markdown=markdown, ocr_pages=ocr_pages),
    )

    assert result.classification == classification
    assert result.classification_confidence == 0.91
    assert result.page_count == 2
    assert result.provider == "pdf-inspector"
    assert result.provider_version == "test-0.2.6"
    assert result.status == ("success" if upstream_type == "text_based" else "ocr_needed")


def test_mixed_pdf_preserves_text_pages_and_marks_ocr_pages() -> None:
    result = extract_structured_pdf(
        "fixture.pdf",
        inspector=FakeInspector(
            pdf_type="mixed",
            page_markdown=["Extracted first page", "", "Extracted third page"],
            ocr_pages=[2],
        ),
    )

    assert result.status == "ocr_needed"
    assert result.classification == "mixed"
    assert result.ocr_needed_pages == [2]
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert [page.state for page in result.pages] == ["success", "ocr_needed", "success"]
    assert result.pages[0].markdown == "Extracted first page"
    assert result.pages[0].positioned_text[0].page_number == 1
    assert result.pages[1].ocr_reasons == ["no_text_operators"]
    assert "Extracted third page" in result.text


def test_normalizes_mixed_upstream_page_indexes_to_one_based() -> None:
    inspector = FakeInspector(pdf_type="mixed", page_markdown=["one", "two"], ocr_pages=[2])

    result = extract_structured_pdf("fixture.pdf", inspector=inspector)

    assert result.pages[1].page_number == 2
    assert result.pages[1].markdown == "two"
    assert result.pages[1].positioned_text[0].page_number == 2
    serialized = result.to_dict()
    assert serialized["pages"][1]["page_number"] == 2
    assert serialized["pages"][1]["positioned_text"][0]["page_number"] == 2


def test_canonical_projection_is_deterministic_and_page_ordered() -> None:
    structured = StructuredPdfExtraction(
        status="success",
        pages=[
            StructuredPdfPage(page_number=3, state="success", markdown=" Third "),
            StructuredPdfPage(page_number=1, state="success", text=" First "),
            StructuredPdfPage(page_number=2, state="success", markdown=" Second "),
        ],
        markdown="document-level fallback",
    )

    assert canonical_full_text_projection(structured) == "First\n\nSecond\n\nThird"
    assert canonical_full_text_projection(structured) == canonical_full_text_projection(structured)


def test_pdf_inspector_projection_wins_before_compatibility_providers(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    structured = StructuredPdfExtraction(
        status="success",
        classification="text",
        page_count=1,
        pages=[StructuredPdfPage(page_number=1, state="success", markdown="# Canonical")],
        provider_version="test-0.2.6",
    )

    class UnexpectedMarkItDown:
        def __init__(self) -> None:
            raise AssertionError("MarkItDown must not run after structured extraction succeeds")

    monkeypatch.setattr("ingest.text_extractor.extract_structured_pdf", lambda path: structured)
    monkeypatch.setattr("ingest.text_extractor.MarkItDown", UnexpectedMarkItDown)

    result = extract_full_text_from_pdf(pdf_path)

    assert result.text == "# Canonical"
    assert result.source == "pdf-inspector"
    assert result.provider == "pdf-inspector"
    assert result.provider_version == "test-0.2.6"
    assert result.content_format == "markdown"
    assert result.attempted_methods == ["pdf-inspector"]


class FakePage:
    def extract_text(self) -> str:
        return "compatibility text"


class FakePdfReader:
    def __init__(self, path: str) -> None:
        self.pages = [FakePage()]


def test_default_provider_unavailable_uses_compatibility_fallback(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr("ingest.pdf_inspector_adapter._pdf_inspector", None)
    monkeypatch.setattr("ingest.text_extractor.MarkItDown", None)
    monkeypatch.setattr("ingest.text_extractor.PdfReader", FakePdfReader)

    result = extract_full_text_from_pdf(pdf_path)

    assert result.status == "success"
    assert result.source == "pypdf"
    assert result.text == "compatibility text"
    assert result.structured_extraction is not None
    assert result.structured_extraction.status == "not_extracted"
    assert result.attempted_methods == ["pypdf"]


def test_pdf_inspector_failure_keeps_pypdf_fallback_available(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    structured_failure = StructuredPdfExtraction(
        status="failed",
        errors=["pdf-inspector: simulated failure"],
    )
    monkeypatch.setattr("ingest.text_extractor.extract_structured_pdf", lambda path: structured_failure)
    monkeypatch.setattr("ingest.text_extractor.MarkItDown", None)
    monkeypatch.setattr("ingest.text_extractor.PdfReader", FakePdfReader)

    result = extract_full_text_from_pdf(pdf_path)

    assert result.status == "success"
    assert result.source == "pypdf"
    assert result.attempted_methods == ["pdf-inspector", "pypdf"]
    assert "pdf-inspector: simulated failure" in result.errors


def test_ocr_needed_is_not_reported_as_extraction_failure(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    structured = StructuredPdfExtraction(
        status="ocr_needed",
        classification="scanned",
        page_count=1,
        ocr_needed_pages=[1],
    )
    monkeypatch.setattr("ingest.text_extractor.extract_structured_pdf", lambda path: structured)
    monkeypatch.setattr("ingest.text_extractor.MarkItDown", None)
    monkeypatch.setattr("ingest.text_extractor.PdfReader", None)

    result = extract_full_text_from_pdf(pdf_path)

    assert result.status == "ocr_needed"
    assert result.source == "none"
    assert result.char_count == 0
    assert result.structured_extraction == structured
