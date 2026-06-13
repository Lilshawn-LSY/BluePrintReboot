from ingest.doi_extractor import (
    extract_doi_candidates_from_filename,
    extract_doi_candidates_from_pdf,
    extract_doi_candidates_from_text,
)
from tests.helpers import make_workspace


def test_extract_doi_candidates_from_text_common_patterns() -> None:
    text = """
    DOI: 10.1000/ABC.Def
    Also available at https://doi.org/10.5555/Example-2.
    Duplicate doi:10.1000/abc.def
    """

    assert extract_doi_candidates_from_text(text) == [
        "10.1000/abc.def",
        "10.5555/example-2",
    ]


def test_extract_doi_from_nature_header_url() -> None:
    assert extract_doi_candidates_from_text("Article https://doi.org/10.1038/s41589-023-01430-2") == [
        "10.1038/s41589-023-01430-2"
    ]


def test_extract_doi_from_article_header_text() -> None:
    text = (
        "Nature Chemical Biology | Volume 19 | December 2023 | 1551-1560\n"
        "Article https://doi.org/10.1038/s41589-023-01430-2\n"
        "Biosynthesis of natural and halogenated plant monoterpene indole alkaloids in yeast"
    )

    assert extract_doi_candidates_from_text(text) == ["10.1038/s41589-023-01430-2"]


def test_extract_doi_candidates_from_text_all_requested_formats() -> None:
    samples = [
        "10.1038/s41589-023-01430-2",
        "https://doi.org/10.1038/s41589-023-01430-2",
        "http://doi.org/10.1038/s41589-023-01430-2",
        "http://dx.doi.org/10.1038/s41589-023-01430-2",
        "DOI: 10.1038/s41589-023-01430-2",
        "doi:10.1038/s41589-023-01430-2",
    ]

    for sample in samples:
        assert extract_doi_candidates_from_text(sample) == ["10.1038/s41589-023-01430-2"]


def test_extract_doi_candidates_from_filename() -> None:
    assert extract_doi_candidates_from_filename("paper_10.1038_s41586-020-2649-2.pdf") == [
        "10.1038/s41586-020-2649-2"
    ]


def test_extract_doi_candidates_from_pdf_missing_file_is_safe() -> None:
    workspace = make_workspace("missing-pdf")
    assert extract_doi_candidates_from_pdf(workspace / "missing.pdf") == []


def test_extract_doi_candidates_from_pdf_corrupt_file_is_safe() -> None:
    workspace = make_workspace("corrupt-pdf")
    pdf_path = workspace / "corrupt.pdf"
    pdf_path.write_text("not a pdf", encoding="utf-8")

    assert extract_doi_candidates_from_pdf(pdf_path) == []
