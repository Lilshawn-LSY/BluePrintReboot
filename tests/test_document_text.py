from ingest.document_text import get_text_extraction_backends


def test_get_text_extraction_backends_reports_import_status(monkeypatch) -> None:
    monkeypatch.setattr("ingest.document_text.PdfReader", object())
    monkeypatch.setattr("ingest.document_text.MarkItDown", None)

    assert get_text_extraction_backends() == {
        "pypdf": True,
        "markitdown": False,
    }
