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


def pending_note_save_result_key(paper_id: str) -> str:
    return _key("pending_note_save_result", paper_id)


def pending_note_save_notice_key(paper_id: str) -> str:
    return _key("pending_note_save_notice", paper_id)


def reader_note_session_keys(paper_id: str) -> tuple[str, ...]:
    return (
        note_draft_key(paper_id),
        note_baseline_key(paper_id),
        note_saved_at_key(paper_id),
        pending_note_reload_key(paper_id),
        pending_note_discard_reload_key(paper_id),
        pending_note_text_update_key(paper_id),
        pending_note_header_refresh_key(paper_id),
        pending_note_block_append_key(paper_id),
        pending_note_notice_key(paper_id),
        pending_note_save_result_key(paper_id),
        pending_note_save_notice_key(paper_id),
    )


def discard_reader_note_session(paper_id: str, session_state) -> None:
    for key in reader_note_session_keys(paper_id):
        session_state.pop(key, None)


def activate_reader_paper(paper_id: str, session_state, *, page_name: str = "Paper Detail") -> bool:
    target = str(paper_id or "").strip()
    previous = str(session_state.get("active_paper_id", "") or "").strip()
    changed = bool(previous and target and previous != target)
    if changed:
        discard_reader_note_session(previous, session_state)
    if target:
        session_state["active_paper_id"] = target
    session_state["current_page"] = page_name
    return changed
