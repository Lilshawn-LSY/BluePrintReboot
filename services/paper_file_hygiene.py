from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Callable, Mapping

import pandas as pd

from storage.index_store import load_index, save_index
from storage.paths import INDEX_CSV, PAPERS_DIR


MAX_FILENAME_LENGTH = 180
SHORT_TITLE_WORD_LIMIT = 7
_PDF_EXTENSION = ".pdf"
_INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_YEAR = re.compile(r"(?<!\d)(?:1[5-9]\d{2}|20\d{2}|21\d{2})(?!\d)")


class PaperFileHygieneError(RuntimeError):
    def __init__(self, message: str, plan: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.plan = plan


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _clean_text(value: object) -> str:
    cleaned = _INVALID_WINDOWS_CHARS.sub(" ", _text(value))
    cleaned = _WHITESPACE.sub(" ", cleaned).strip(" .")
    return cleaned


def sanitize_filename_component(value: object) -> str:
    """Return a Windows-safe filename component with spaces as underscores."""
    return _clean_text(value).replace(" ", "_").strip(" ._")


def extract_year(record: Mapping[str, object]) -> str:
    match = _YEAR.search(_text(record.get("year", "")))
    return match.group(0) if match else ""


def extract_first_author(record: Mapping[str, object]) -> str:
    authors = _clean_text(record.get("authors", ""))
    if not authors:
        return ""

    if ";" in authors:
        first_author = authors.split(";", 1)[0].strip()
    else:
        first_author = authors.split(",", 1)[0].strip()

    if "," in first_author:
        surname = first_author.split(",", 1)[0].strip()
    else:
        tokens = first_author.split()
        surname = tokens[-1] if tokens else first_author

    return sanitize_filename_component(surname or first_author)


def extract_short_title(
    record: Mapping[str, object],
    word_limit: int = SHORT_TITLE_WORD_LIMIT,
) -> str:
    title = _text(record.get("title", ""))
    if title.lower().endswith(_PDF_EXTENSION):
        title = title[: -len(_PDF_EXTENSION)]
    cleaned = _clean_text(title)
    words = [word for word in cleaned.split(" ") if word]
    return sanitize_filename_component(" ".join(words[:word_limit]))


def _safe_paper_id_short(paper_id: object) -> str:
    safe_id = sanitize_filename_component(paper_id)
    return safe_id[:12].strip(" ._") or "paper"


def _is_safe_pdf_filename(filename: str) -> bool:
    return bool(
        filename
        and filename.lower().endswith(_PDF_EXTENSION)
        and filename == Path(filename).name
        and not _INVALID_WINDOWS_CHARS.search(filename)
        and not filename[:-len(_PDF_EXTENSION)].endswith((" ", "."))
        and filename[:-len(_PDF_EXTENSION)].strip(" ._")
    )


def _limit_pdf_filename(stem: str, max_filename_length: int) -> str:
    if max_filename_length <= len(_PDF_EXTENSION):
        raise ValueError("max_filename_length must leave room for a filename stem")
    max_stem_length = max_filename_length - len(_PDF_EXTENSION)
    limited_stem = stem[:max_stem_length].rstrip(" ._")
    return f"{limited_stem}{_PDF_EXTENSION}"


def build_recommended_filename(
    record: Mapping[str, object],
    max_filename_length: int = MAX_FILENAME_LENGTH,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    year = extract_year(record)
    author = extract_first_author(record)
    title = extract_short_title(record)

    if not year:
        year = "UnknownYear"
        warnings.append("Year metadata is missing; using UnknownYear.")
    if not author:
        author = "UnknownAuthor"
        warnings.append("Author metadata is missing; using UnknownAuthor.")
    if not title:
        title = "Untitled"
        warnings.append("Title metadata is missing; using Untitled.")

    stem = "_".join(part for part in (year, author, title) if part).strip(" ._")
    filename = _limit_pdf_filename(stem, max_filename_length)
    if not _is_safe_pdf_filename(filename):
        fallback_stem = (
            f"UnknownYear_UnknownAuthor_Untitled_{_safe_paper_id_short(record.get('paper_id', ''))}"
        )
        filename = _limit_pdf_filename(fallback_stem, max_filename_length)
        warnings.append("Generated metadata filename was unsafe; using a paper_id-based fallback.")
    return filename, warnings


def _record_path(record: Mapping[str, object], papers_dir: Path) -> Path:
    filepath = _text(record.get("filepath", ""))
    filename = _text(record.get("filename", ""))
    if filepath:
        path = Path(filepath)
        if path.is_absolute():
            return path
        return Path(papers_dir) / path
    return Path(papers_dir) / filename


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def suggest_available_filename(target_path: Path) -> str:
    for suffix in range(2, 10_000):
        candidate = target_path.with_name(f"{target_path.stem}_{suffix}{target_path.suffix}")
        if not candidate.exists():
            return candidate.name
    return ""


def build_rename_plan(
    record: Mapping[str, object],
    papers_dir: Path = PAPERS_DIR,
    max_filename_length: int = MAX_FILENAME_LENGTH,
) -> dict[str, object]:
    paper_id = _text(record.get("paper_id", ""))
    current_filename = _text(record.get("filename", ""))
    recommended_filename, warnings = build_recommended_filename(record, max_filename_length)
    missing_year_and_author = not extract_year(record) and not extract_first_author(record)
    if missing_year_and_author and current_filename.lower().endswith(_PDF_EXTENSION):
        recommended_filename = current_filename
    current_path = _record_path(record, Path(papers_dir))
    target_path = current_path.with_name(recommended_filename)

    status = "ok"
    can_apply = True
    if not paper_id or not current_filename or not _is_safe_pdf_filename(recommended_filename):
        status = "invalid"
        can_apply = False
        if not paper_id:
            warnings.append("paper_id is missing; rename cannot be applied safely.")
        if not current_filename:
            warnings.append("Current filename is missing from the paper index.")
    elif not current_path.exists() or not current_path.is_file():
        status = "source_missing"
        can_apply = False
        warnings.append("The indexed source PDF could not be found.")
    elif missing_year_and_author:
        status = "insufficient_metadata"
        can_apply = False
    elif _same_path(current_path, target_path):
        status = "unchanged"
        can_apply = False
    elif target_path.exists():
        status = "collision_blocked"
        can_apply = False
        suggestion = suggest_available_filename(target_path)
        warning = "The recommended target filename already exists; no file will be overwritten."
        if suggestion:
            warning += f" An available alternative is {suggestion}."
        warnings.append(warning)
    elif warnings:
        status = "missing_metadata"

    return {
        "paper_id": paper_id,
        "current_filename": current_filename,
        "recommended_filename": recommended_filename,
        "current_path": str(current_path.resolve(strict=False)),
        "target_path": str(target_path.resolve(strict=False)),
        "status": status,
        "warnings": warnings,
        "can_apply": can_apply,
    }


def _default_rename(source: Path, target: Path) -> None:
    source.rename(target)


def _restore_index_bytes(index_csv: Path, contents: bytes) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=index_csv.parent, delete=False) as temporary:
            temporary.write(contents)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, index_csv)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def apply_paper_file_rename(
    paper_id: str,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    *,
    index_loader: Callable[[Path], pd.DataFrame] | None = None,
    index_writer: Callable[[pd.DataFrame, Path], None] | None = None,
    rename_file: Callable[[Path, Path], None] | None = None,
) -> dict[str, object]:
    """Apply one previewed-style rename while preserving the existing paper_id."""
    index_csv = Path(index_csv)
    loader = index_loader or load_index
    writer = index_writer or save_index
    rename = rename_file or _default_rename

    dataframe = loader(index_csv)
    matches = dataframe[dataframe["paper_id"] == str(paper_id)]
    if len(matches) != 1:
        raise PaperFileHygieneError(f"Expected one index record for paper_id {paper_id!r}.")

    record = matches.iloc[0].to_dict()
    plan = build_rename_plan(record, papers_dir=Path(papers_dir))
    if not plan["can_apply"]:
        raise PaperFileHygieneError(
            f"Rename is blocked with status {plan['status']}.",
            plan,
        )

    source = Path(str(plan["current_path"]))
    target = Path(str(plan["target_path"]))
    if not source.exists() or not source.is_file():
        plan = build_rename_plan(record, papers_dir=Path(papers_dir))
        raise PaperFileHygieneError("The source PDF no longer exists.", plan)
    if target.exists() and not _same_path(source, target):
        plan = build_rename_plan(record, papers_dir=Path(papers_dir))
        raise PaperFileHygieneError("The target PDF now exists; no file was overwritten.", plan)

    original_index = index_csv.read_bytes()
    try:
        rename(source, target)
    except Exception as exc:
        raise PaperFileHygieneError(f"Could not rename the PDF: {exc}", plan) from exc

    updated = dataframe.copy()
    row_mask = updated["paper_id"] == str(paper_id)
    updated.loc[row_mask, "filename"] = target.name
    updated.loc[row_mask, "filepath"] = str(target.resolve(strict=False))

    try:
        writer(updated, index_csv)
    except Exception as exc:
        recovery_errors: list[str] = []
        try:
            if target.exists() and not source.exists():
                target.rename(source)
        except Exception as rollback_exc:
            recovery_errors.append(f"file rollback failed: {rollback_exc}")
        try:
            if not index_csv.exists() or index_csv.read_bytes() != original_index:
                _restore_index_bytes(index_csv, original_index)
        except Exception as restore_exc:
            recovery_errors.append(f"index restore failed: {restore_exc}")

        detail = f"Could not update paper_index.csv: {exc}."
        if recovery_errors:
            detail += " " + "; ".join(recovery_errors)
        else:
            detail += " The PDF rename and index were rolled back."
        raise PaperFileHygieneError(detail, plan) from exc

    applied_plan = dict(plan)
    applied_plan["applied"] = True
    return applied_plan
