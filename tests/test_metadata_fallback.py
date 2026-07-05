import pandas as pd
import requests

from services.metadata_fallback import (
    apply_metadata_candidate_to_index,
    build_doi_less_metadata_candidate,
    extract_arxiv_id_from_text,
    lookup_arxiv_metadata,
    normalize_arxiv_id,
    parse_arxiv_atom_metadata,
)
from storage.index_store import load_index, save_index
from tests.helpers import make_workspace


class FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <published>2017-06-12T17:57:34Z</published>
    <updated>2017-12-05T00:00:00Z</updated>
    <title>
      Attention Is All You Need
    </title>
    <summary>
      The dominant sequence transduction models are based on complex recurrent or convolutional networks.
    </summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <arxiv:doi>10.48550/arXiv.1706.03762</arxiv:doi>
  </entry>
</feed>
"""


def test_arxiv_id_extraction_from_filename() -> None:
    assert extract_arxiv_id_from_text("Attention_1706.03762v3.pdf") == "1706.03762"
    assert extract_arxiv_id_from_text("arXiv_2301.12345_preprint.pdf") == "2301.12345"


def test_arxiv_id_extraction_from_pdf_text_and_version_normalization() -> None:
    candidate = build_doi_less_metadata_candidate(
        {"filename": "paper.pdf", "filepath": ""},
        pdf_text="Preprint\narXiv:2301.12345v2\nA title follows",
        lookup_arxiv=False,
    )

    assert candidate["arxiv_id"] == "2301.12345"
    assert candidate["source"] == "arxiv_id"
    assert candidate["year"] == "2023"


def test_old_style_arxiv_id_normalization() -> None:
    assert normalize_arxiv_id("arXiv:hep-th/9901001v4") == "hep-th/9901001"
    assert normalize_arxiv_id("cs/9901001") == "cs/9901001"


def test_arxiv_detection_avoids_ordinary_years_and_random_numbers() -> None:
    text = "Published in 2024 with 1234567 samples. Version 2024.12345 was internal."

    assert extract_arxiv_id_from_text(text) == ""


def test_mocked_arxiv_metadata_parse_success() -> None:
    candidate = parse_arxiv_atom_metadata(ARXIV_ATOM, fallback_arxiv_id="1706.03762")

    assert candidate["title"] == "Attention Is All You Need"
    assert candidate["authors"] == "Ashish Vaswani; Noam Shazeer"
    assert candidate["year"] == "2017"
    assert candidate["abstract"].startswith("The dominant sequence transduction models")
    assert candidate["doi"] == "10.48550/arxiv.1706.03762"
    assert candidate["arxiv_id"] == "1706.03762"
    assert candidate["source"] == "arxiv_id"
    assert candidate["confidence"] == "high"


def test_arxiv_lookup_uses_mocked_response() -> None:
    def fake_get(url, headers, timeout):
        assert "id_list=1706.03762" in url
        assert headers["User-Agent"].startswith("BluePrintReboot/")
        assert timeout > 0
        return FakeResponse(ARXIV_ATOM)

    candidate = lookup_arxiv_metadata("arXiv:1706.03762v7", request_get=fake_get)

    assert candidate["title"] == "Attention Is All You Need"
    assert candidate["arxiv_id"] == "1706.03762"
    assert candidate["confidence"] == "high"


def test_arxiv_network_failure_returns_diagnostic_without_crashing() -> None:
    def fail_get(url, headers, timeout):
        raise requests.exceptions.ConnectionError()

    candidate = lookup_arxiv_metadata("2301.12345", request_get=fail_get)

    assert candidate["arxiv_id"] == "2301.12345"
    assert candidate["source"] == "arxiv_id"
    assert candidate["confidence"] == "medium"
    assert "network connection failed" in " ".join(candidate["diagnostics"])


def test_candidate_apply_does_not_overwrite_existing_non_empty_metadata() -> None:
    workspace = make_workspace("metadata-fallback-no-overwrite")
    index_csv = workspace / "data" / "paper_index.csv"
    save_index(
        pd.DataFrame(
            [
                {
                    "paper_id": "paper-1",
                    "filename": "Existing.pdf",
                    "filepath": "Existing.pdf",
                    "title": "Manual Title",
                    "authors": "Manual Author",
                    "year": "",
                    "abstract": "",
                    "doi": "",
                }
            ]
        ),
        index_csv,
    )

    result = apply_metadata_candidate_to_index(
        "paper-1",
        {
            "title": "Candidate Title",
            "authors": "Candidate Author",
            "year": "2024",
            "abstract": "Candidate abstract",
            "doi": "10.48550/arXiv.2301.12345",
            "source": "arxiv_id",
            "confidence": "high",
        },
        index_csv=index_csv,
    )

    row = load_index(index_csv).iloc[0]
    assert row["title"] == "Manual Title"
    assert row["authors"] == "Manual Author"
    assert row["year"] == "2024"
    assert row["abstract"] == "Candidate abstract"
    assert row["doi"] == "10.48550/arxiv.2301.12345"
    assert result["skipped_existing_fields"] == {
        "title": "Manual Title",
        "authors": "Manual Author",
    }


def test_candidate_apply_fills_empty_metadata() -> None:
    workspace = make_workspace("metadata-fallback-fill-empty")
    index_csv = workspace / "data" / "paper_index.csv"
    save_index(
        pd.DataFrame(
            [
                {
                    "paper_id": "paper-1",
                    "filename": "Untitled.pdf",
                    "filepath": "Untitled.pdf",
                    "title": "Untitled",
                    "authors": "",
                    "year": "",
                    "abstract": "",
                }
            ]
        ),
        index_csv,
    )

    apply_metadata_candidate_to_index(
        "paper-1",
        {
            "authors": "Candidate Author",
            "year": "2025",
            "abstract": "Candidate abstract",
            "source": "pdf_text_guess",
            "confidence": "low",
        },
        index_csv=index_csv,
    )

    row = load_index(index_csv).iloc[0]
    assert row["authors"] == "Candidate Author"
    assert row["year"] == "2025"
    assert row["abstract"] == "Candidate abstract"
    assert row["metadata_source"] == "pdf_text_guess"
    assert row["metadata_confidence"] == "low"
