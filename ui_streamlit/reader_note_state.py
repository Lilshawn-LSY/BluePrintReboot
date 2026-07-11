from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, MutableMapping


def _key(kind: str, paper_id: str) -> str:
    return f"{kind}_{paper_id}"


def note_draft_key(paper_id: str) -> str:
    return _key("reader_note_draft", paper_id)


def note_baseline_key(paper_id: str) -> str:
    return _key("reader_note_baseline", paper_id)


def note_saved_at_key(paper_id: str) -> str:
    return _key("reader_note_saved_at", paper_id)


def pending_note_reload_key(paper_id: str) -> str:
    return _key("pending_note_reload", paper_id)


def pending_note_discard_reload_key(paper_id: str) -> str:
    return _key("pending_note_discard_reload", paper_id)


def pending_note_text_update_key(paper_id: str) -> str:
    return _key("pending_note_text_update", paper_id)


def pending_note_header_refresh_key(paper_id: str) -> str:
    return _key("pending_note_header_refresh", paper_id)


def pending_note_block_append_key(paper_id: str) -> str:
    return _key("pending_note_block_append", paper_id)


def pending_note_notice_key(paper_id: str) -> str:
    return _key("pending_note_notice", paper_id)


@dataclass(frozen=True)
class ReaderNoteState:
    paper_id: str
    draft: str
    baseline: str
    dirty: bool
    header_refresh_pending: bool
    discard_reload_pending: bool

    @property
    def label(self) -> str:
        return "Unsaved changes" if self.dirty else "Saved"


def derive_reader_note_state(paper_id: str, session_state: MutableMapping) -> ReaderNoteState:
    draft = str(session_state.get(note_draft_key(paper_id), ""))
    baseline = str(session_state.get(note_baseline_key(paper_id), ""))
    return ReaderNoteState(
        paper_id=paper_id,
        draft=draft,
        baseline=baseline,
        dirty=draft != baseline,
        header_refresh_pending=bool(session_state.get(pending_note_header_refresh_key(paper_id))),
        discard_reload_pending=bool(session_state.get(pending_note_discard_reload_key(paper_id))),
    )


def initialize_reader_note_state(paper_id: str, session_state: MutableMapping, disk_text: str) -> str:
    draft_key = note_draft_key(paper_id)
    baseline_key = note_baseline_key(paper_id)
    if draft_key not in session_state:
        session_state[draft_key] = str(disk_text)
        session_state[baseline_key] = str(disk_text)
    elif baseline_key not in session_state:
        session_state[baseline_key] = str(disk_text)
    return str(session_state[draft_key])


def mark_reader_note_saved(paper_id: str, session_state: MutableMapping, saved_at: str) -> None:
    session_state[note_baseline_key(paper_id)] = str(session_state.get(note_draft_key(paper_id), ""))
    session_state[note_saved_at_key(paper_id)] = str(saved_at)
    session_state.pop(pending_note_discard_reload_key(paper_id), None)
    session_state.pop(pending_note_reload_key(paper_id), None)


def request_note_reload(paper_id: str, session_state: MutableMapping) -> str:
    if derive_reader_note_state(paper_id, session_state).dirty:
        session_state.pop(pending_note_reload_key(paper_id), None)
        session_state[pending_note_discard_reload_key(paper_id)] = True
        session_state[pending_note_notice_key(paper_id)] = "Reload needs confirmation; unsaved changes kept."
        return "confirmation_required"
    session_state.pop(pending_note_discard_reload_key(paper_id), None)
    session_state[pending_note_reload_key(paper_id)] = "clean"
    return "queued"


def resolve_note_reload(paper_id: str, session_state: MutableMapping, *, discard: bool) -> bool:
    confirmation_key = pending_note_discard_reload_key(paper_id)
    if not session_state.pop(confirmation_key, None):
        return False
    session_state.pop(pending_note_reload_key(paper_id), None)
    if discard:
        session_state[pending_note_reload_key(paper_id)] = "discard"
        session_state[pending_note_notice_key(paper_id)] = "Unsaved changes discarded; reloading note."
    else:
        session_state[pending_note_notice_key(paper_id)] = "Reload cancelled; draft kept."
    return True


def apply_queued_reload(paper_id: str, session_state: MutableMapping, disk_text: str) -> bool:
    reload_event = session_state.pop(pending_note_reload_key(paper_id), None)
    if not reload_event:
        return False
    destructive_reload_accepted = reload_event == "discard"
    if derive_reader_note_state(paper_id, session_state).dirty and not destructive_reload_accepted:
        session_state[pending_note_discard_reload_key(paper_id)] = True
        session_state[pending_note_notice_key(paper_id)] = "Reload needs confirmation; unsaved changes kept."
        return False
    session_state[note_draft_key(paper_id)] = str(disk_text)
    session_state[note_baseline_key(paper_id)] = str(disk_text)
    session_state.pop(pending_note_discard_reload_key(paper_id), None)
    session_state[pending_note_notice_key(paper_id)] = "Note reloaded."
    return True


def queue_note_text_replacement(
    paper_id: str,
    session_state: MutableMapping,
    text: str,
) -> None:
    session_state[pending_note_text_update_key(paper_id)] = {
        "text": str(text),
        "expected_draft": str(session_state.get(note_draft_key(paper_id), "")),
    }


def apply_queued_content_updates(
    paper_id: str,
    session_state: MutableMapping,
    append_text: Callable[[str, str], str],
) -> str:
    draft_key = note_draft_key(paper_id)
    draft = str(session_state.get(draft_key, ""))
    pending_update = session_state.pop(pending_note_text_update_key(paper_id), None)
    if pending_update is not None:
        if isinstance(pending_update, dict):
            replacement = str(pending_update.get("text", ""))
            expected_draft = str(pending_update.get("expected_draft", draft))
        else:
            replacement = str(pending_update)
            expected_draft = draft
        if draft == expected_draft:
            draft = replacement
            session_state[draft_key] = draft
        else:
            session_state[pending_note_notice_key(paper_id)] = "Draft update skipped; newer edits kept."

    pending_append = str(session_state.pop(pending_note_block_append_key(paper_id), "") or "")
    if pending_append:
        draft = append_text(draft, pending_append)
        session_state[draft_key] = draft
    return draft
