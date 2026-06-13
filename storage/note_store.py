from __future__ import annotations

from pathlib import Path
from typing import Mapping

from storage.paths import NOTES_DIR


def note_path_for(record: Mapping[str, str], notes_dir: Path = NOTES_DIR) -> Path:
    return Path(notes_dir) / f"{record['paper_id']}.md"


def default_note_text(record: Mapping[str, str]) -> str:
    title = record.get("title") or record.get("filename") or "Untitled"
    filename = record.get("filename", "")
    status = record.get("status", "unread")
    return f"""# {title}

## Bibliographic Info
- Filename: {filename}
- Status: {status}

## One-line Summary

## Key Claims

## Methods

## Evidence

## Limitations

## Future Ideas

## Links to My Projects
"""


def create_note_if_missing(record: Mapping[str, str], notes_dir: Path = NOTES_DIR) -> Path:
    note_path = note_path_for(record, notes_dir)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    if not note_path.exists():
        note_path.write_text(default_note_text(record), encoding="utf-8")
    return note_path


def load_note_text(record: Mapping[str, str], notes_dir: Path = NOTES_DIR) -> str:
    note_path = create_note_if_missing(record, notes_dir)
    return note_path.read_text(encoding="utf-8")


def save_note_text(record: Mapping[str, str], text: str, notes_dir: Path = NOTES_DIR) -> Path:
    note_path = note_path_for(record, notes_dir)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(text, encoding="utf-8")
    return note_path
