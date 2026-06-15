from ingest.text_extractor import extract_full_text_from_pdf
from tests.helpers import make_workspace


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakePdfReader:
    def __init__(self, path: str) -> None:
        self.pages = [FakePage("page one"), FakePage("page two")]


class FailingMarkItDown:
    def convert(self, path: str):
        raise RuntimeError("markitdown failed")


def test_missing_pdf_extraction_returns_safe_failure() -> None:
    result = extract_full_text_from_pdf(make_workspace("missing-text") / "missing.pdf")

    assert result.status == "failed"
    assert result.text == ""
    assert result.source == "none"
    assert result.char_count == 0
    assert result.errors


def test_pypdf_fallback_extracts_text_when_markitdown_unavailable(monkeypatch) -> None:
    workspace = make_workspace("pypdf-text")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr("ingest.text_extractor.MarkItDown", None)
    monkeypatch.setattr("ingest.text_extractor.PdfReader", FakePdfReader)

    result = extract_full_text_from_pdf(pdf_path)

    assert result.status == "success"
    assert result.source == "pypdf"
    assert result.text == "page one\npage two"
    assert result.char_count == len(result.text)
    assert result.attempted_methods == ["pypdf"]


def test_markitdown_failure_with_pypdf_success_is_success_with_diagnostics(monkeypatch) -> None:
    workspace = make_workspace("markitdown-fail-pypdf-success")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr("ingest.text_extractor.MarkItDown", FailingMarkItDown)
    monkeypatch.setattr("ingest.text_extractor.PdfReader", FakePdfReader)

    result = extract_full_text_from_pdf(pdf_path)

    assert result.status == "success"
    assert result.source == "pypdf"
    assert result.errors == ["markitdown: markitdown failed"]
    assert result.attempted_methods == ["markitdown", "pypdf"]
