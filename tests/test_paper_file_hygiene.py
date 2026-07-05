from pathlib import Path

import pandas as pd
import pytest

from services.paper_file_hygiene import (
    PaperFileHygieneError,
    apply_paper_file_rename,
    build_recommended_filename,
    build_rename_plan,
    extract_first_author,
)
from storage.index_store import load_index, save_index, update_index_from_scan
from tests.helpers import make_workspace


def _record(pdf_path: Path, **overrides: str) -> dict[str, str]:
    record = {
        "paper_id": "stable-paper-id-123456",
        "filename": pdf_path.name,
        "filepath": str(pdf_path.resolve()),
        "title": "Deep Learning",
        "authors": "Yann LeCun; Yoshua Bengio; Geoffrey Hinton",
        "year": "2014",
    }
    record.update(overrides)
    return record


def _indexed_paper(name: str = "Original.pdf") -> tuple[Path, Path, Path, str]:
    workspace = make_workspace(name.removesuffix(".pdf").lower())
    papers_dir = workspace / "papers"
    index_csv = workspace / "data" / "paper_index.csv"
    papers_dir.mkdir()
    pdf_path = papers_dir / name
    pdf_path.write_bytes(b"%PDF-1.4\noriginal")
    paper_id = "stable-paper-id-123456"
    save_index(pd.DataFrame([_record(pdf_path, paper_id=paper_id)]), index_csv)
    return papers_dir, index_csv, pdf_path, paper_id


def test_builds_recommended_filename_from_full_metadata() -> None:
    filename, warnings = build_recommended_filename(
        {
            "paper_id": "paper-1",
            "title": "Deep Learning",
            "authors": "Yann LeCun; Yoshua Bengio; Geoffrey Hinton",
            "year": "2014",
        }
    )

    assert filename == "2014_LeCun_Deep_Learning.pdf"
    assert warnings == []


@pytest.mark.parametrize(
    ("authors", "expected"),
    [
        ("Yann LeCun; Yoshua Bengio; Geoffrey Hinton", "LeCun"),
        ("LeCun, Yann; Bengio, Yoshua", "LeCun"),
        ("Yann LeCun, Yoshua Bengio", "LeCun"),
    ],
)
def test_extract_first_author_handles_common_formats(authors: str, expected: str) -> None:
    assert extract_first_author({"authors": authors}) == expected


def test_windows_invalid_characters_and_controls_are_sanitized() -> None:
    filename, _ = build_recommended_filename(
        {
            "paper_id": "paper-1",
            "title": 'A: Study / of <Unsafe> "Names"?*\x07',
            "authors": "Yann / LeCun",
            "year": "2014",
        }
    )

    assert filename == "2014_LeCun_A_Study_of_Unsafe_Names.pdf"
    assert not any(character in filename for character in '<>:"/\\|?*')
    assert "\x07" not in filename


def test_whitespace_is_collapsed_and_replaced_with_underscores() -> None:
    filename, _ = build_recommended_filename(
        {
            "paper_id": "paper-1",
            "title": "  Deep\t Learning  for\n Vision  ",
            "authors": "  Yann    LeCun  ",
            "year": " 2014 ",
        }
    )

    assert filename == "2014_LeCun_Deep_Learning_for_Vision.pdf"


def test_pdf_extension_is_preserved_once() -> None:
    filename, _ = build_recommended_filename(
        {"paper_id": "paper-1", "title": "Deep Learning.PDF", "authors": "Yann LeCun", "year": "2014"}
    )

    assert filename == "2014_LeCun_Deep_Learning.pdf"
    assert filename.lower().count(".pdf") == 1


def test_filename_length_is_limited_without_losing_pdf_extension() -> None:
    filename, _ = build_recommended_filename(
        {
            "paper_id": "paper-1",
            "title": "One two three four five six seven extremelylongword" * 5,
            "authors": "Yann LeCun",
            "year": "2014",
        },
        max_filename_length=48,
    )

    assert len(filename) <= 48
    assert filename.endswith(".pdf")


@pytest.mark.parametrize(
    ("field", "expected_part", "warning_part"),
    [
        ("year", "UnknownYear", "Year metadata is missing"),
        ("authors", "UnknownAuthor", "Author metadata is missing"),
        ("title", "Untitled", "Title metadata is missing"),
    ],
)
def test_missing_metadata_uses_safe_fallbacks(field: str, expected_part: str, warning_part: str) -> None:
    record = {"paper_id": "paper-1", "title": "Deep Learning", "authors": "Yann LeCun", "year": "2014"}
    record[field] = ""

    filename, warnings = build_recommended_filename(record)

    assert expected_part in filename
    assert any(warning_part in warning for warning in warnings)


def test_plan_blocks_collision_without_overwriting() -> None:
    papers_dir, _, current_path, _ = _indexed_paper("Collision Original.pdf")
    target = papers_dir / "2014_LeCun_Deep_Learning.pdf"
    target.write_bytes(b"existing target")

    plan = build_rename_plan(_record(current_path), papers_dir=papers_dir)

    assert plan["status"] == "collision_blocked"
    assert plan["can_apply"] is False
    assert "_2.pdf" in " ".join(plan["warnings"])


def test_plan_is_unchanged_when_current_filename_matches_recommendation() -> None:
    workspace = make_workspace("unchanged-filename")
    papers_dir = workspace / "papers"
    papers_dir.mkdir()
    pdf_path = papers_dir / "2014_LeCun_Deep_Learning.pdf"
    pdf_path.write_bytes(b"%PDF")

    plan = build_rename_plan(_record(pdf_path), papers_dir=papers_dir)

    assert plan["status"] == "unchanged"
    assert plan["can_apply"] is False


def test_plan_reports_missing_source() -> None:
    workspace = make_workspace("missing-source")
    missing_path = workspace / "papers" / "Missing.pdf"

    plan = build_rename_plan(_record(missing_path), papers_dir=missing_path.parent)

    assert plan["status"] == "source_missing"
    assert plan["can_apply"] is False


def test_plan_allows_missing_metadata_after_warning() -> None:
    workspace = make_workspace("missing-metadata-plan")
    papers_dir = workspace / "papers"
    papers_dir.mkdir()
    pdf_path = papers_dir / "Original.pdf"
    pdf_path.write_bytes(b"%PDF")

    plan = build_rename_plan(_record(pdf_path, year=""), papers_dir=papers_dir)

    assert plan["status"] == "missing_metadata"
    assert plan["can_apply"] is True


def test_plan_allows_untitled_fallback_when_only_title_is_missing() -> None:
    workspace = make_workspace("missing-title-plan")
    papers_dir = workspace / "papers"
    papers_dir.mkdir()
    pdf_path = papers_dir / "Original.pdf"
    pdf_path.write_bytes(b"%PDF")

    plan = build_rename_plan(_record(pdf_path, title=""), papers_dir=papers_dir)

    assert plan["status"] == "missing_metadata"
    assert plan["can_apply"] is True
    assert plan["recommended_filename"] == "2014_LeCun_Untitled.pdf"
    assert any("Title metadata is missing" in warning for warning in plan["warnings"])


def test_plan_blocks_placeholder_rename_when_year_and_author_are_missing() -> None:
    workspace = make_workspace("insufficient-metadata-plan")
    papers_dir = workspace / "papers"
    papers_dir.mkdir()
    pdf_path = papers_dir / "Readable Existing Filename.pdf"
    pdf_path.write_bytes(b"%PDF")

    plan = build_rename_plan(
        _record(
            pdf_path,
            title="Readable Existing Filename",
            year="",
            authors="",
        ),
        papers_dir=papers_dir,
    )

    assert plan["status"] == "insufficient_metadata"
    assert plan["can_apply"] is False
    assert plan["recommended_filename"] == pdf_path.name
    assert "UnknownYear_UnknownAuthor" not in str(plan["recommended_filename"])
    assert any("Year metadata is missing" in warning for warning in plan["warnings"])
    assert any("Author metadata is missing" in warning for warning in plan["warnings"])


def test_apply_blocks_unknown_year_and_author_rename() -> None:
    workspace = make_workspace("insufficient-metadata-apply")
    papers_dir = workspace / "papers"
    index_csv = workspace / "data" / "paper_index.csv"
    papers_dir.mkdir()
    pdf_path = papers_dir / "Keep This Filename.pdf"
    pdf_path.write_bytes(b"%PDF original")
    paper_id = "stable-paper-id-123456"
    save_index(
        pd.DataFrame(
            [
                _record(
                    pdf_path,
                    paper_id=paper_id,
                    title="Keep This Filename",
                    year="",
                    authors="",
                )
            ]
        ),
        index_csv,
    )
    original_index = index_csv.read_bytes()

    with pytest.raises(PaperFileHygieneError, match="insufficient_metadata"):
        apply_paper_file_rename(paper_id, index_csv=index_csv, papers_dir=papers_dir)

    assert pdf_path.read_bytes() == b"%PDF original"
    assert index_csv.read_bytes() == original_index


def test_successful_rename_updates_only_target_row_and_preserves_paper_id() -> None:
    papers_dir, index_csv, source, paper_id = _indexed_paper("Successful Original.pdf")
    unrelated_path = papers_dir / "Unrelated.pdf"
    unrelated_path.write_bytes(b"%PDF unrelated")
    dataframe = load_index(index_csv)
    unrelated = _record(
        unrelated_path,
        paper_id="unrelated-paper-id",
        title="Unrelated Paper",
        authors="Ada Lovelace",
        year="1843",
    )
    dataframe = pd.concat([dataframe, pd.DataFrame([unrelated])], ignore_index=True)
    save_index(dataframe, index_csv)
    unrelated_before = load_index(index_csv).loc[lambda df: df["paper_id"] == "unrelated-paper-id"].iloc[0].to_dict()

    result = apply_paper_file_rename(paper_id, index_csv=index_csv, papers_dir=papers_dir)

    target = papers_dir / "2014_LeCun_Deep_Learning.pdf"
    updated = load_index(index_csv)
    renamed_row = updated[updated["paper_id"] == paper_id].iloc[0]
    unrelated_after = updated[updated["paper_id"] == "unrelated-paper-id"].iloc[0].to_dict()
    assert result["applied"] is True
    assert not source.exists()
    assert target.read_bytes() == b"%PDF-1.4\noriginal"
    assert renamed_row["paper_id"] == paper_id
    assert renamed_row["filename"] == target.name
    assert renamed_row["filepath"] == str(target.resolve())
    assert unrelated_after == unrelated_before


def test_successful_rename_does_not_touch_paper_id_backed_files() -> None:
    papers_dir, index_csv, _, paper_id = _indexed_paper("Identity Original.pdf")
    workspace = papers_dir.parent
    identity_files = [
        workspace / "notes" / f"{paper_id}.md",
        workspace / "data" / "note_blocks" / f"{paper_id}.json",
        workspace / "data" / "extracted_text" / f"{paper_id}.txt",
    ]
    for path in identity_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("identity sentinel", encoding="utf-8")

    apply_paper_file_rename(paper_id, index_csv=index_csv, papers_dir=papers_dir)

    assert all(path.read_text(encoding="utf-8") == "identity sentinel" for path in identity_files)


def test_apply_never_overwrites_an_existing_target() -> None:
    papers_dir, index_csv, source, paper_id = _indexed_paper("Blocked Original.pdf")
    target = papers_dir / "2014_LeCun_Deep_Learning.pdf"
    target.write_bytes(b"keep me")
    original_index = index_csv.read_bytes()

    with pytest.raises(PaperFileHygieneError, match="collision_blocked"):
        apply_paper_file_rename(paper_id, index_csv=index_csv, papers_dir=papers_dir)

    assert source.exists()
    assert target.read_bytes() == b"keep me"
    assert index_csv.read_bytes() == original_index


def test_failed_physical_rename_does_not_modify_index() -> None:
    papers_dir, index_csv, source, paper_id = _indexed_paper("Physical Failure.pdf")
    original_index = index_csv.read_bytes()

    def fail_rename(source_path: Path, target_path: Path) -> None:
        raise OSError("simulated rename failure")

    with pytest.raises(PaperFileHygieneError, match="simulated rename failure"):
        apply_paper_file_rename(
            paper_id,
            index_csv=index_csv,
            papers_dir=papers_dir,
            rename_file=fail_rename,
        )

    assert source.exists()
    assert index_csv.read_bytes() == original_index


def test_index_write_failure_restores_index_and_rolls_back_file() -> None:
    papers_dir, index_csv, source, paper_id = _indexed_paper("Index Failure.pdf")
    original_index = index_csv.read_bytes()

    def corrupt_then_fail(dataframe: pd.DataFrame, path: Path) -> None:
        path.write_bytes(b"corrupted")
        raise OSError("simulated index failure")

    with pytest.raises(PaperFileHygieneError, match="rolled back"):
        apply_paper_file_rename(
            paper_id,
            index_csv=index_csv,
            papers_dir=papers_dir,
            index_writer=corrupt_then_fail,
        )

    assert source.exists()
    assert not (papers_dir / "2014_LeCun_Deep_Learning.pdf").exists()
    assert index_csv.read_bytes() == original_index


def test_rescan_preserves_paper_id_after_hygiene_rename() -> None:
    papers_dir, index_csv, _, paper_id = _indexed_paper("Rescan Original.pdf")
    notes_dir = papers_dir.parent / "notes"
    notes_dir.mkdir()

    apply_paper_file_rename(paper_id, index_csv=index_csv, papers_dir=papers_dir)
    rescanned = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(rescanned) == 1
    assert rescanned.iloc[0]["paper_id"] == paper_id
