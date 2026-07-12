from __future__ import annotations

import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ingest.doi import normalize_doi
from ingest.scanner import (
    PDF_HASH_METADATA_FIELDS,
    extract_doi_metadata_from_pdf,
    pdf_hash_metadata_key,
    pdf_sha256_with_metadata,
    scan_papers,
)
from storage.paths import INDEX_CSV, NOTES_DIR, PAPERS_DIR, ensure_workspace_dirs


INDEX_COLUMNS = [
    "paper_id",
    "filename",
    "filepath",
    "pdf_sha256",
    "pdf_size_bytes",
    "pdf_modified_at",
    "title",
    "authors",
    "year",
    "journal",
    "doi",
    "abstract",
    "keywords",
    "tags",
    "status",
    "reading_priority",
    "is_archived",
    "archived_at",
    "doi_source",
    "extraction_source",
    "extraction_checked_at",
    "metadata_source",
    "metadata_confidence",
    "metadata_checked_at",
    "text_status",
    "text_source",
    "text_char_count",
    "text_extracted_at",
    "note_path",
    "added_at",
    "updated_at",
]

DEFAULT_VALUES = {
    "authors": "",
    "year": "",
    "journal": "",
    "doi": "",
    "abstract": "",
    "keywords": "",
    "tags": "",
    "status": "unread",
    "reading_priority": "normal",
    "is_archived": "false",
    "archived_at": "",
    "doi_source": "",
    "extraction_source": "",
    "extraction_checked_at": "",
    "pdf_size_bytes": "",
    "pdf_modified_at": "",
    "metadata_source": "",
    "metadata_confidence": "",
    "metadata_checked_at": "",
    "text_status": "",
    "text_source": "",
    "text_char_count": "",
    "text_extracted_at": "",
}

USER_EDITABLE_COLUMNS = [
    "title",
    "authors",
    "year",
    "journal",
    "doi",
    "abstract",
    "keywords",
    "tags",
    "status",
    "reading_priority",
]

SYSTEM_MUTABLE_COLUMNS = [
    "doi_source",
    "extraction_source",
    "extraction_checked_at",
]

TEXT_EXTRACTION_COLUMNS = [
    "text_status",
    "text_source",
    "text_char_count",
    "text_extracted_at",
]

EDITABLE_METADATA_COLUMNS = USER_EDITABLE_COLUMNS + SYSTEM_MUTABLE_COLUMNS + TEXT_EXTRACTION_COLUMNS

CROSSREF_ACCEPT_COLUMNS = [
    "title",
    "authors",
    "year",
    "journal",
    "doi",
    "abstract",
    "keywords",
    "metadata_source",
    "metadata_confidence",
    "metadata_checked_at",
]

SYSTEM_COLUMNS = [
    "paper_id",
    "filename",
    "filepath",
    "pdf_sha256",
    "pdf_size_bytes",
    "pdf_modified_at",
    "note_path",
    "added_at",
    "updated_at",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_index() -> pd.DataFrame:
    return pd.DataFrame(columns=INDEX_COLUMNS)


def _default_for_column(column: str, row: pd.Series) -> str:
    if column == "title":
        filename = row.get("filename", "")
        return Path(filename).stem if filename else ""
    if column == "note_path":
        paper_id = row.get("paper_id", "")
        return str((NOTES_DIR / f"{paper_id}.md").resolve()) if paper_id else ""
    if column in ("added_at", "updated_at"):
        return _now_iso()
    return DEFAULT_VALUES.get(column, "")


def migrate_index_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    migrated = df.copy().fillna("")
    for column in INDEX_COLUMNS:
        if column not in migrated.columns:
            migrated[column] = ""

    for index, row in migrated.iterrows():
        for column in INDEX_COLUMNS:
            if str(migrated.at[index, column]) == "":
                migrated.at[index, column] = _default_for_column(column, row)

    migrated["doi"] = migrated["doi"].apply(normalize_doi)
    ordered = INDEX_COLUMNS + [column for column in migrated.columns if column not in INDEX_COLUMNS]
    return migrated[ordered]


def _infer_papers_dir(index_csv: Path) -> Path:
    index_csv = Path(index_csv).resolve(strict=False)
    if index_csv.parent.name.lower() == "data":
        return index_csv.parent.parent / "papers"
    return PAPERS_DIR


def _record_pdf_path(row: pd.Series, papers_dir: Path) -> Path | None:
    filepath = str(row.get("filepath", "")).strip()
    filename = str(row.get("filename", "")).strip()
    if filepath:
        path = Path(filepath)
        return path if path.is_absolute() else Path(papers_dir) / path
    if filename:
        return Path(papers_dir) / filename
    return None


def backfill_pdf_sha256(df: pd.DataFrame, papers_dir: Path) -> pd.DataFrame:
    backfilled = df.copy().fillna("")
    for column in PDF_HASH_METADATA_FIELDS:
        if column not in backfilled.columns:
            backfilled[column] = ""
    for index, row in backfilled.iterrows():
        pdf_path = _record_pdf_path(row, Path(papers_dir))
        if pdf_path is None or not pdf_path.exists() or not pdf_path.is_file():
            continue
        try:
            hash_metadata = pdf_sha256_with_metadata(pdf_path, row.to_dict())
        except OSError:
            continue
        for column in PDF_HASH_METADATA_FIELDS:
            backfilled.at[index, column] = hash_metadata[column]
    return backfilled


def ensure_index(index_csv: Path = INDEX_CSV) -> None:
    ensure_workspace_dirs()
    index_csv = Path(index_csv)
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    if not index_csv.exists():
        save_index(empty_index(), index_csv)


def load_index(index_csv: Path = INDEX_CSV, papers_dir: Path | None = None) -> pd.DataFrame:
    ensure_index(index_csv)
    df = pd.read_csv(index_csv, dtype=str).fillna("")
    migrated = migrate_index_dataframe(df)
    backfilled = backfill_pdf_sha256(migrated, papers_dir or _infer_papers_dir(index_csv))
    if list(df.columns) != list(backfilled.columns) or df.shape != backfilled.shape or not df.equals(backfilled):
        save_index(backfilled, index_csv)
    return backfilled


def save_index(df: pd.DataFrame, index_csv: Path = INDEX_CSV) -> None:
    index_csv = Path(index_csv)
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    output = backfill_pdf_sha256(migrate_index_dataframe(df), _infer_papers_dir(index_csv))
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=index_csv.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            output.to_csv(temporary, index=False)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, index_csv)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def update_index_from_scan(
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    notes_dir: Path = NOTES_DIR,
) -> pd.DataFrame:
    df = load_index(index_csv, papers_dir=papers_dir)
    existing_records = df.to_dict("records")
    existing_by_path = {
        pdf_hash_metadata_key(str(record.get("filepath", ""))): record
        for record in existing_records
        if str(record.get("filepath", "")).strip()
    }
    scanned = scan_papers(
        papers_dir=papers_dir,
        notes_dir=notes_dir,
        hash_metadata_by_path=existing_by_path,
    )
    existing_by_hash: dict[str, list[dict[str, str]]] = {}
    for record in existing_records:
        digest = str(record.get("pdf_sha256", "")).strip()
        if digest:
            existing_by_hash.setdefault(digest, []).append(record)

    scanned_hash_counts = Counter(str(record.get("pdf_sha256", "")).strip() for record in scanned)
    records_to_apply: list[dict[str, str]] = []
    unmatched: list[dict[str, str]] = []
    claimed_existing_ids: set[str] = set()
    for record in scanned:
        existing = existing_by_path.get(pdf_hash_metadata_key(record["filepath"]))
        if existing is not None:
            record["paper_id"] = str(existing.get("paper_id", ""))
            record["note_path"] = str(existing.get("note_path", ""))
            claimed_existing_ids.add(record["paper_id"])
            records_to_apply.append(record)
        else:
            unmatched.append(record)

    for record in unmatched:
        digest = str(record.get("pdf_sha256", "")).strip()
        hash_matches = existing_by_hash.get(digest, []) if digest else []
        matched_claimed_record = any(
            str(match.get("paper_id", "")) in claimed_existing_ids for match in hash_matches
        )
        if digest and len(hash_matches) == 1 and scanned_hash_counts[digest] == 1:
            existing = hash_matches[0]
            existing_id = str(existing.get("paper_id", ""))
            if existing_id not in claimed_existing_ids:
                record["paper_id"] = existing_id
                record["note_path"] = str(existing.get("note_path", ""))
                claimed_existing_ids.add(existing_id)
                records_to_apply.append(record)
                continue
        if digest and hash_matches and (matched_claimed_record or len(hash_matches) != 1 or scanned_hash_counts[digest] != 1):
            continue
        records_to_apply.append(record)

    scanned_by_id = {record["paper_id"]: record for record in records_to_apply}
    existing_ids = set(df["paper_id"].tolist())

    for paper_id, record in scanned_by_id.items():
        if paper_id in existing_ids:
            row_mask = df["paper_id"] == paper_id
            for column in ("filename", "filepath", "pdf_sha256", "pdf_size_bytes", "pdf_modified_at", "note_path"):
                df.loc[row_mask, column] = record[column]
            if (df.loc[row_mask, "title"] == "").any():
                df.loc[row_mask, "title"] = record["title"]
            df.loc[row_mask, "updated_at"] = _now_iso()
        else:
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)

    save_index(df, index_csv)
    return df


def enrich_paper_doi_from_pdf(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path | None = None,
    overwrite_existing: bool = False,
) -> dict[str, str | bool]:
    df = load_index(index_csv, papers_dir=papers_dir)
    row_mask = df["paper_id"] == paper_id
    if not row_mask.any():
        return {
            "paper_id": paper_id,
            "doi": "",
            "source": "none",
            "saved": False,
            "status": "missing_paper",
            "message": "Paper was not found in the index.",
        }

    record = df[row_mask].iloc[0]
    current_doi = normalize_doi(str(record.get("doi", "") or ""))
    if current_doi and not overwrite_existing:
        return {
            "paper_id": paper_id,
            "doi": current_doi,
            "source": str(record.get("doi_source", "") or "existing"),
            "saved": False,
            "status": "existing_doi",
            "message": "Existing DOI used; PDF extraction was not needed.",
        }

    inferred_papers_dir = papers_dir or _infer_papers_dir(index_csv)
    pdf_path = _record_pdf_path(record, inferred_papers_dir)
    if pdf_path is None or not pdf_path.exists() or not pdf_path.is_file():
        return {
            "paper_id": paper_id,
            "doi": "",
            "source": "none",
            "saved": False,
            "status": "missing_pdf",
            "message": "PDF file was not found; DOI extraction was not attempted.",
        }

    extraction = extract_doi_metadata_from_pdf(pdf_path)
    checked_at = _now_iso()
    df.loc[row_mask, "extraction_source"] = extraction.source
    df.loc[row_mask, "extraction_checked_at"] = checked_at
    saved = False
    status = "doi_not_found"
    message = "No DOI detected. You can paste one manually."
    detected_doi = normalize_doi(extraction.doi)
    if detected_doi:
        df.loc[row_mask, "doi"] = detected_doi
        df.loc[row_mask, "doi_source"] = extraction.source
        saved = True
        status = "doi_saved"
        message = "Detected DOI was saved to this paper."
    df.loc[row_mask, "updated_at"] = checked_at
    save_index(df, index_csv)
    return {
        "paper_id": paper_id,
        "doi": detected_doi,
        "source": extraction.source,
        "saved": saved,
        "status": status,
        "message": message,
    }


def update_paper_status(paper_id: str, status: str, index_csv: Path = INDEX_CSV) -> pd.DataFrame:
    return update_paper_metadata(paper_id, {"status": status}, index_csv)


def set_paper_archived(paper_id: str, archived: bool, index_csv: Path = INDEX_CSV) -> pd.DataFrame:
    df = load_index(index_csv)
    row_mask = df["paper_id"] == paper_id
    if not row_mask.any():
        return df
    df.loc[row_mask, "is_archived"] = "true" if archived else "false"
    df.loc[row_mask, "archived_at"] = _now_iso() if archived else ""
    df.loc[row_mask, "updated_at"] = _now_iso()
    save_index(df, index_csv)
    return load_index(index_csv)


def filter_archived(df: pd.DataFrame, *, include_archived: bool = False, archived_only: bool = False) -> pd.DataFrame:
    values = df.get("is_archived", pd.Series("false", index=df.index)).astype(str).str.lower() == "true"
    if archived_only:
        return df[values].copy()
    if include_archived:
        return df.copy()
    return df[~values].copy()


def update_paper_metadata(
    paper_id: str,
    metadata: dict[str, str],
    index_csv: Path = INDEX_CSV,
) -> pd.DataFrame:
    df = load_index(index_csv)
    row_mask = df["paper_id"] == paper_id
    if not row_mask.any():
        return df

    for column in EDITABLE_METADATA_COLUMNS:
        if column in metadata:
            value = str(metadata[column]).strip()
            if column == "doi":
                value = normalize_doi(value)
                df.loc[row_mask, "doi_source"] = str(metadata.get("doi_source", "manual" if value else "")).strip()
            df.loc[row_mask, column] = value
    df.loc[row_mask, "updated_at"] = _now_iso()
    save_index(df, index_csv)
    return load_index(index_csv)


def accept_crossref_metadata(
    paper_id: str,
    metadata: dict[str, str],
    index_csv: Path = INDEX_CSV,
) -> pd.DataFrame:
    df = load_index(index_csv)
    row_mask = df["paper_id"] == paper_id
    if not row_mask.any():
        return df

    for column in CROSSREF_ACCEPT_COLUMNS:
        if column in metadata:
            value = str(metadata[column]).strip()
            if not value:
                continue
            if column == "doi":
                value = normalize_doi(value)
                df.loc[row_mask, "doi_source"] = str(metadata.get("doi_source", "crossref" if value else "")).strip()
            df.loc[row_mask, column] = value
    df.loc[row_mask, "updated_at"] = _now_iso()
    save_index(df, index_csv)
    return load_index(index_csv)
