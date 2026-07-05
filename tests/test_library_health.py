import hashlib
from pathlib import Path

import pandas as pd

from services.library_health import run_library_health_check
from tests.helpers import make_workspace


def _workspace(name: str) -> tuple[Path, Path, Path, Path, Path, Path]:
    workspace = make_workspace(name)
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    note_blocks_dir = workspace / "data" / "note_blocks"
    projects_dir = workspace / "data" / "projects"
    extracted_text_dir = workspace / "data" / "extracted_text"
    index_csv = workspace / "data" / "paper_index.csv"
    for directory in (papers_dir, notes_dir, note_blocks_dir, projects_dir, extracted_text_dir):
        directory.mkdir(parents=True)
    return papers_dir, notes_dir, note_blocks_dir, projects_dir, extracted_text_dir, index_csv


def _run_health(paths: tuple[Path, Path, Path, Path, Path, Path]):
    papers_dir, notes_dir, note_blocks_dir, projects_dir, extracted_text_dir, index_csv = paths
    return run_library_health_check(
        index_csv=index_csv,
        papers_dir=papers_dir,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
        extracted_text_dir=extracted_text_dir,
    )


def _record(paper_id: str, pdf_path: Path, doi: str = "") -> dict[str, str]:
    return {
        "paper_id": paper_id,
        "filename": pdf_path.name,
        "filepath": str(pdf_path.resolve()),
        "title": f"Title {paper_id}",
        "authors": "Author Name",
        "year": "2024",
        "doi": doi,
    }


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def test_health_check_detects_missing_indexed_pdf() -> None:
    paths = _workspace("health-missing-pdf")
    index_csv = paths[-1]
    missing_pdf = paths[0] / "Missing.pdf"
    pd.DataFrame([_record("paper-1", missing_pdf)]).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert report["healthy"] is False
    assert report["missing_pdfs"] == [
        {
            "paper_id": "paper-1",
            "filename": "Missing.pdf",
            "filepath": str(missing_pdf.resolve()),
        }
    ]


def test_health_check_detects_unindexed_pdf() -> None:
    paths = _workspace("health-unindexed-pdf")
    papers_dir, *_, index_csv = paths
    unindexed = papers_dir / "Unindexed.pdf"
    unindexed.write_bytes(b"%PDF-1.4\n")
    pd.DataFrame(columns=["paper_id", "filename", "filepath", "title", "authors", "year", "doi"]).to_csv(
        index_csv, index=False
    )

    report = _run_health(paths)

    assert report["unindexed_pdfs"] == [str(unindexed.resolve())]


def test_health_check_detects_normalized_duplicate_doi() -> None:
    paths = _workspace("health-duplicate-doi")
    papers_dir, *_, index_csv = paths
    first_pdf = papers_dir / "First.pdf"
    second_pdf = papers_dir / "Second.pdf"
    first_pdf.write_bytes(b"%PDF-1.4\nfirst")
    second_pdf.write_bytes(b"%PDF-1.4\nsecond")
    pd.DataFrame(
        [
            _record("paper-1", first_pdf, "10.1000/ABC"),
            _record("paper-2", second_pdf, "https://doi.org/10.1000/abc"),
        ]
    ).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert report["duplicate_dois"] == [
        {
            "doi": "10.1000/abc",
            "count": 2,
            "paper_ids": "paper-1, paper-2",
        }
    ]


def test_health_check_reports_duplicate_pdf_hash_for_unindexed_copy() -> None:
    paths = _workspace("health-duplicate-pdf-hash")
    papers_dir, *_, index_csv = paths
    contents = b"%PDF-1.4\nsame content"
    indexed_pdf = papers_dir / "Indexed.pdf"
    duplicate_pdf = papers_dir / "Duplicate.pdf"
    indexed_pdf.write_bytes(contents)
    duplicate_pdf.write_bytes(contents)
    record = _record("paper-1", indexed_pdf)
    record["pdf_sha256"] = _sha256(contents)
    pd.DataFrame([record]).to_csv(index_csv, index=False)

    report = _run_health(paths)

    assert report["unindexed_pdfs"] == [str(duplicate_pdf.resolve())]
    assert report["duplicate_pdf_hashes"] == [
        {
            "pdf_sha256": _sha256(contents),
            "count": 2,
            "paper_ids": "paper-1",
            "filenames": "Indexed.pdf, Duplicate.pdf",
            "filepaths": f"{indexed_pdf.resolve()} | {duplicate_pdf.resolve()}",
            "indexed": "yes, no",
        }
    ]
