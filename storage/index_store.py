from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ingest.doi import normalize_doi
from ingest.scanner import scan_papers
from storage.paths import INDEX_CSV, NOTES_DIR, PAPERS_DIR, ensure_workspace_dirs


INDEX_COLUMNS = [
    "paper_id",
    "filename",
    "filepath",
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
    "doi_source": "",
    "extraction_source": "",
    "extraction_checked_at": "",
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


def ensure_index(index_csv: Path = INDEX_CSV) -> None:
    ensure_workspace_dirs()
    index_csv = Path(index_csv)
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    if not index_csv.exists():
        save_index(empty_index(), index_csv)


def load_index(index_csv: Path = INDEX_CSV) -> pd.DataFrame:
    ensure_index(index_csv)
    df = pd.read_csv(index_csv, dtype=str).fillna("")
    migrated = migrate_index_dataframe(df)
    if list(df.columns) != list(migrated.columns) or df.shape != migrated.shape or not df.equals(migrated):
        save_index(migrated, index_csv)
    return migrated


def save_index(df: pd.DataFrame, index_csv: Path = INDEX_CSV) -> None:
    index_csv = Path(index_csv)
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    output = migrate_index_dataframe(df)
    output.to_csv(index_csv, index=False)


def update_index_from_scan(
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    notes_dir: Path = NOTES_DIR,
) -> pd.DataFrame:
    df = load_index(index_csv)
    scanned = scan_papers(papers_dir=papers_dir, notes_dir=notes_dir)
    scanned_by_id = {record["paper_id"]: record for record in scanned}
    existing_ids = set(df["paper_id"].tolist())

    for paper_id, record in scanned_by_id.items():
        if paper_id in existing_ids:
            row_mask = df["paper_id"] == paper_id
            for column in ("filename", "filepath", "note_path"):
                df.loc[row_mask, column] = record[column]
            if (df.loc[row_mask, "title"] == "").any():
                df.loc[row_mask, "title"] = record["title"]
            if record.get("doi") and (df.loc[row_mask, "doi"] == "").any():
                df.loc[row_mask, "doi"] = normalize_doi(record["doi"])
                df.loc[row_mask, "doi_source"] = record.get("doi_source", "")
            df.loc[row_mask, "extraction_source"] = record.get("extraction_source", "")
            df.loc[row_mask, "extraction_checked_at"] = record.get("extraction_checked_at", "")
            df.loc[row_mask, "updated_at"] = _now_iso()
        else:
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)

    save_index(df, index_csv)
    return df


def update_paper_status(paper_id: str, status: str, index_csv: Path = INDEX_CSV) -> pd.DataFrame:
    return update_paper_metadata(paper_id, {"status": status}, index_csv)


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
            if column == "doi":
                value = normalize_doi(value)
                df.loc[row_mask, "doi_source"] = str(metadata.get("doi_source", "crossref" if value else "")).strip()
            df.loc[row_mask, column] = value
    df.loc[row_mask, "updated_at"] = _now_iso()
    save_index(df, index_csv)
    return load_index(index_csv)
