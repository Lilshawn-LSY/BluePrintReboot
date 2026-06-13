from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ingest.scanner import scan_papers
from storage.paths import INDEX_CSV, NOTES_DIR, PAPERS_DIR, ensure_workspace_dirs


INDEX_COLUMNS = [
    "paper_id",
    "filename",
    "filepath",
    "title",
    "status",
    "note_path",
    "added_at",
    "updated_at",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_index() -> pd.DataFrame:
    return pd.DataFrame(columns=INDEX_COLUMNS)


def ensure_index(index_csv: Path = INDEX_CSV) -> None:
    ensure_workspace_dirs()
    index_csv = Path(index_csv)
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    if not index_csv.exists():
        save_index(empty_index(), index_csv)


def load_index(index_csv: Path = INDEX_CSV) -> pd.DataFrame:
    ensure_index(index_csv)
    df = pd.read_csv(index_csv, dtype=str).fillna("")
    for column in INDEX_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[INDEX_COLUMNS]


def save_index(df: pd.DataFrame, index_csv: Path = INDEX_CSV) -> None:
    index_csv = Path(index_csv)
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    output = df.copy()
    for column in INDEX_COLUMNS:
        if column not in output.columns:
            output[column] = ""
    output[INDEX_COLUMNS].to_csv(index_csv, index=False)


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
            for column in ("filename", "filepath", "title", "note_path"):
                df.loc[row_mask, column] = record[column]
            if (df.loc[row_mask, "status"] == "missing").any():
                df.loc[row_mask, "status"] = "unread"
            df.loc[row_mask, "updated_at"] = _now_iso()
        else:
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)

    scanned_paths = {record["filepath"] for record in scanned}
    missing_mask = (df["filepath"] != "") & ~df["filepath"].isin(scanned_paths)
    df.loc[missing_mask, "status"] = "missing"
    save_index(df, index_csv)
    return df


def update_paper_status(paper_id: str, status: str, index_csv: Path = INDEX_CSV) -> pd.DataFrame:
    df = load_index(index_csv)
    row_mask = df["paper_id"] == paper_id
    if row_mask.any():
        df.loc[row_mask, "status"] = status
        df.loc[row_mask, "updated_at"] = _now_iso()
        save_index(df, index_csv)
    return df
