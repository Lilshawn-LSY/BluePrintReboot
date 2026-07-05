import hashlib

from ingest.scanner import extract_doi_from_pdf, extract_doi_metadata_from_pdf, scan_papers
from tests.helpers import make_workspace


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakePdfReader:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages


class FakeMarkItDownResult:
    def __init__(self, text_content: str) -> None:
        self.text_content = text_content


class FakeMarkItDown:
    def __init__(self, text_content: str = "") -> None:
        self.text_content = text_content

    def convert(self, path: str) -> FakeMarkItDownResult:
        return FakeMarkItDownResult(self.text_content)


def test_scan_papers_returns_pdf_records() -> None:
    workspace = make_workspace("scanner-records")
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    papers_dir.mkdir()
    notes_dir.mkdir()
    contents = b"%PDF-1.4\n"
    (papers_dir / "Example Paper.pdf").write_bytes(contents)
    (papers_dir / "ignore.txt").write_text("not a pdf", encoding="utf-8")

    records = scan_papers(papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(records) == 1
    record = records[0]
    assert record["filename"] == "Example Paper.pdf"
    assert record["title"] == "Example Paper"
    assert record["authors"] == ""
    assert record["year"] == ""
    assert record["journal"] == ""
    assert record["doi"] == ""
    assert record["abstract"] == ""
    assert record["keywords"] == ""
    assert record["tags"] == ""
    assert record["status"] == "unread"
    assert record["reading_priority"] == "normal"
    assert record["doi_source"] == ""
    assert record["pdf_sha256"] == hashlib.sha256(contents).hexdigest()
    assert record["extraction_source"] == "none"
    assert record["extraction_checked_at"]
    assert record["metadata_source"] == ""
    assert record["metadata_confidence"] == ""
    assert record["metadata_checked_at"] == ""
    assert record["paper_id"].startswith("example-paper-")
    assert record["note_path"].endswith(".md")


def test_scan_papers_uses_stable_ids() -> None:
    workspace = make_workspace("scanner-stable")
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    papers_dir.mkdir()
    notes_dir.mkdir()
    (papers_dir / "Stable.pdf").write_bytes(b"%PDF-1.4\n")

    first = scan_papers(papers_dir=papers_dir, notes_dir=notes_dir)
    second = scan_papers(papers_dir=papers_dir, notes_dir=notes_dir)

    assert first[0]["paper_id"] == second[0]["paper_id"]


def test_extract_doi_from_pdf_detects_and_normalizes(monkeypatch) -> None:
    workspace = make_workspace("scanner-doi")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        "ingest.document_text.PdfReader",
        lambda path: FakePdfReader([FakePage("Full text DOI 10.1111/PCE.13021.")]),
    )

    assert extract_doi_from_pdf(pdf_path) == "10.1111/pce.13021"


def test_extract_doi_metadata_from_pdf_reports_pypdf_source(monkeypatch) -> None:
    workspace = make_workspace("scanner-doi-source")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "ingest.document_text.PdfReader",
        lambda path: FakePdfReader([FakePage("Full text DOI 10.1111/PCE.13021.")]),
    )

    result = extract_doi_metadata_from_pdf(pdf_path)

    assert result.doi == "10.1111/pce.13021"
    assert result.source == "pypdf"


def test_extract_doi_metadata_from_pdf_uses_markitdown_after_pypdf_no_doi(monkeypatch) -> None:
    workspace = make_workspace("scanner-doi-markitdown")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "ingest.document_text.PdfReader",
        lambda path: FakePdfReader([FakePage("No identifier in this text.")]),
    )
    monkeypatch.setattr(
        "ingest.document_text.MarkItDown",
        lambda: FakeMarkItDown("Visible first page text doi: 10.1111/PCE.13021."),
    )

    result = extract_doi_metadata_from_pdf(pdf_path)

    assert result.doi == "10.1111/pce.13021"
    assert result.source == "markitdown"


def test_extract_doi_metadata_from_pdf_handles_markitdown_unavailable(monkeypatch) -> None:
    workspace = make_workspace("scanner-doi-markitdown-unavailable")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "ingest.document_text.PdfReader",
        lambda path: FakePdfReader([FakePage("No identifier in this text.")]),
    )
    monkeypatch.setattr("ingest.document_text.MarkItDown", None)

    result = extract_doi_metadata_from_pdf(pdf_path)

    assert result.doi == ""
    assert result.source == "none"


def test_extract_doi_from_pdf_returns_empty_when_text_extraction_fails(monkeypatch) -> None:
    workspace = make_workspace("scanner-doi-failure")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    def fail_reader(path):
        raise ValueError("cannot read pdf text")

    monkeypatch.setattr("ingest.document_text.PdfReader", fail_reader)
    monkeypatch.setattr("ingest.document_text.MarkItDown", None)

    assert extract_doi_from_pdf(pdf_path) == ""
