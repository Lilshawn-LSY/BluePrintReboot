from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from storage.paths import NOTES_DIR, PAPERS_DIR


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_stem(stem: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return cleaned or "paper"


def make_paper_id(pdf_path: Path, papers_dir: Path = PAPERS_DIR) -> str:
    relative_path = pdf_path.relative_to(papers_dir).as_posix().lower()
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:10]
    return f"{_safe_stem(pdf_path.stem)}-{digest}"


def scan_papers(
    papers_dir: Path = PAPERS_DIR,
    notes_dir: Path = NOTES_DIR,
) -> list[dict[str, str]]:
    papers_dir = Path(papers_dir)
    notes_dir = Path(notes_dir)
    if not papers_dir.exists():
        return []

    scanned_at = _now_iso()
    records: list[dict[str, str]] = []
    for pdf_path in sorted(papers_dir.rglob("*.pdf"), key=lambda path: path.as_posix().lower()):
        paper_id = make_paper_id(pdf_path, papers_dir)
        records.append(
            {
                "paper_id": paper_id,
                "filename": pdf_path.name,
                "filepath": str(pdf_path.resolve()),
                "title": pdf_path.stem,
                "authors": "",
                "year": "",
                "journal": "",
                "doi": "",
                "doi_source": "",
                "doi_extracted_at": "",
                "tags": "",
                "status": "unread",
                "reading_priority": "normal",
                "metadata_source": "",
                "metadata_confidence": "",
                "metadata_checked_at": "",
                "note_path": str((notes_dir / f"{paper_id}.md").resolve()),
                "added_at": scanned_at,
                "updated_at": scanned_at,
            }
        )
    return records
