from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, MutableMapping

from ingest.doi import normalize_doi
from ingest.tag_suggester import merge_tags
from services.reader_state_keys import (
    note_baseline_key,
    note_draft_key,
    pending_note_header_refresh_key,
    pending_note_notice_key,
)
from services.reading_note_template import refresh_reading_note_header
from storage.index_store import CROSSREF_ACCEPT_COLUMNS, EDITABLE_METADATA_COLUMNS, load_index, save_index
from storage.note_store import refresh_note_header
from storage.paths import INDEX_CSV, NOTES_DIR


CANONICAL_NOTE_HEADER_FIELDS = frozenset({"title", "authors", "year", "doi", "tags"})
MUTABLE_METADATA_FIELDS = frozenset({*EDITABLE_METADATA_COLUMNS, *CROSSREF_ACCEPT_COLUMNS})


@dataclass(frozen=True)
class MetadataMutationResult:
    paper_id: str
    status: str
    paper_found: bool
    index_updated: bool
    changed_fields: tuple[str, ...] = ()
    note_sync: str = "not_required"
    note_changed: bool = False
    header_refresh_queued: bool = False
    draft_dirty: bool = False
    updated_record: dict[str, str] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status in {"applied", "no_op"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_change(field_name: str, value: object) -> str:
    text = str(value or "").strip()
    if field_name == "doi":
        return normalize_doi(text)
    if field_name == "tags":
        return merge_tags("", [item.strip() for item in text.split(",") if item.strip()])
    return text


def _record(dataframe, paper_id: str) -> dict[str, str] | None:
    matches = dataframe[dataframe["paper_id"] == paper_id]
    if matches.empty:
        return None
    return {str(key): str(value) for key, value in matches.iloc[0].fillna("").to_dict().items()}


def apply_paper_metadata_change(
    paper_id: str,
    changes: dict[str, object],
    *,
    session_state: MutableMapping[str, object] | None = None,
    index_csv: Path = INDEX_CSV,
    notes_dir: Path = NOTES_DIR,
) -> MetadataMutationResult:
    dataframe = load_index(index_csv)
    current = _record(dataframe, paper_id)
    if current is None:
        return MetadataMutationResult(paper_id=paper_id, status="missing_paper", paper_found=False, index_updated=False)

    normalized = {
        field_name: _normalize_change(field_name, value)
        for field_name, value in changes.items()
        if field_name in MUTABLE_METADATA_FIELDS
    }
    if "doi" in normalized and "doi_source" not in normalized and normalized["doi"] != current.get("doi", ""):
        normalized["doi_source"] = "manual" if normalized["doi"] else ""
    effective = {field_name: value for field_name, value in normalized.items() if current.get(field_name, "") != value}
    if not effective:
        return MetadataMutationResult(
            paper_id=paper_id,
            status="no_op",
            paper_found=True,
            index_updated=False,
            updated_record=current,
        )

    row_mask = dataframe["paper_id"] == paper_id
    for field_name, value in effective.items():
        dataframe.loc[row_mask, field_name] = value
    dataframe.loc[row_mask, "updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        save_index(dataframe, index_csv)
        updated = _record(load_index(index_csv), paper_id) or {**current, **effective}
    except Exception as exc:
        return MetadataMutationResult(
            paper_id=paper_id,
            status="index_write_failed",
            paper_found=True,
            index_updated=False,
            changed_fields=tuple(effective),
            updated_record=current,
            errors=(f"{exc.__class__.__name__}: {exc}",),
        )

    header_fields_changed = bool(CANONICAL_NOTE_HEADER_FIELDS.intersection(effective))
    if not header_fields_changed:
        return MetadataMutationResult(
            paper_id=paper_id,
            status="applied",
            paper_found=True,
            index_updated=True,
            changed_fields=tuple(effective),
            updated_record=updated,
        )

    draft_key = note_draft_key(paper_id)
    baseline_key = note_baseline_key(paper_id)
    draft_exists = session_state is not None and draft_key in session_state
    draft = str(session_state.get(draft_key, "")) if draft_exists and session_state is not None else ""
    baseline = str(session_state.get(baseline_key, "")) if draft_exists and session_state is not None else ""
    draft_dirty = draft_exists and draft != baseline
    if draft_dirty and session_state is not None:
        refreshed = refresh_reading_note_header(draft, updated)
        if refreshed["changed"]:
            session_state[pending_note_header_refresh_key(paper_id)] = {
                "text": str(refreshed["text"]),
                "notice": "Header refresh available; unsaved changes kept.",
                "saved_to_file": False,
            }
            session_state[pending_note_notice_key(paper_id)] = "Header refresh available; unsaved changes kept."
        return MetadataMutationResult(
            paper_id=paper_id,
            status="applied",
            paper_found=True,
            index_updated=True,
            changed_fields=tuple(effective),
            note_sync="queued_dirty_draft",
            note_changed=bool(refreshed["changed"]),
            header_refresh_queued=bool(refreshed["changed"]),
            draft_dirty=True,
            updated_record=updated,
        )

    try:
        note_result = refresh_note_header(updated, notes_dir=notes_dir)
    except Exception as exc:
        return MetadataMutationResult(
            paper_id=paper_id,
            status="partial_failure",
            paper_found=True,
            index_updated=True,
            changed_fields=tuple(effective),
            note_sync="failed",
            updated_record=updated,
            errors=(f"{exc.__class__.__name__}: {exc}",),
        )

    if draft_exists and session_state is not None and note_result["changed"]:
        session_state[pending_note_header_refresh_key(paper_id)] = {
            "text": str(note_result["text"]),
            "notice": "Header refreshed.",
            "saved_to_file": True,
        }
    return MetadataMutationResult(
        paper_id=paper_id,
        status="applied",
        paper_found=True,
        index_updated=True,
        changed_fields=tuple(effective),
        note_sync="synced",
        note_changed=bool(note_result["changed"]),
        header_refresh_queued=bool(draft_exists and note_result["changed"]),
        draft_dirty=False,
        updated_record=updated,
    )
