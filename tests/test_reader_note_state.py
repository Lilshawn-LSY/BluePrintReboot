import pytest

from ui_streamlit.reader_note_state import (
    apply_queued_content_updates,
    apply_queued_reload,
    derive_reader_note_state,
    initialize_reader_note_state,
    mark_reader_note_saved,
    note_baseline_key,
    note_draft_key,
    pending_note_block_append_key,
    pending_note_discard_reload_key,
    pending_note_reload_key,
    pending_note_text_update_key,
    queue_note_text_replacement,
    request_note_reload,
    resolve_note_reload,
)


@pytest.mark.parametrize(
    ("draft", "baseline", "dirty", "label"),
    [
        ("same", "same", False, "Saved"),
        ("edited", "saved", True, "Unsaved changes"),
    ],
)
def test_state_derivation_distinguishes_clean_and_dirty(draft, baseline, dirty, label) -> None:
    state = {
        note_draft_key("paper-1"): draft,
        note_baseline_key("paper-1"): baseline,
    }

    result = derive_reader_note_state("paper-1", state)

    assert result.dirty is dirty
    assert result.label == label


def test_initial_load_and_explicit_save_update_the_baseline() -> None:
    state = {}
    initialize_reader_note_state("paper-1", state, "disk text")
    state[note_draft_key("paper-1")] = "edited text"
    request_note_reload("paper-1", state)

    mark_reader_note_saved("paper-1", state, "2026-07-11T00:00:00Z")

    assert derive_reader_note_state("paper-1", state).dirty is False
    assert state[note_baseline_key("paper-1")] == "edited text"
    assert pending_note_discard_reload_key("paper-1") not in state
    assert pending_note_reload_key("paper-1") not in state


def test_dirty_reload_request_keeps_draft_and_requires_confirmation() -> None:
    state = {
        note_draft_key("paper-1"): "exact unsaved draft",
        note_baseline_key("paper-1"): "saved text",
    }

    outcome = request_note_reload("paper-1", state)

    assert outcome == "confirmation_required"
    assert state[note_draft_key("paper-1")] == "exact unsaved draft"
    assert state[pending_note_discard_reload_key("paper-1")] is True
    assert pending_note_reload_key("paper-1") not in state


def test_discard_confirmation_loads_disk_text_and_updates_baseline() -> None:
    state = {
        note_draft_key("paper-1"): "unsaved",
        note_baseline_key("paper-1"): "old disk",
    }
    request_note_reload("paper-1", state)

    assert resolve_note_reload("paper-1", state, discard=True) is True
    assert apply_queued_reload("paper-1", state, "new disk") is True

    assert state[note_draft_key("paper-1")] == "new disk"
    assert state[note_baseline_key("paper-1")] == "new disk"
    assert derive_reader_note_state("paper-1", state).dirty is False
    assert pending_note_discard_reload_key("paper-1") not in state
    assert pending_note_reload_key("paper-1") not in state


def test_keep_draft_cancels_reload_without_stale_destructive_state() -> None:
    state = {
        note_draft_key("paper-1"): "exact unsaved draft",
        note_baseline_key("paper-1"): "saved text",
    }
    request_note_reload("paper-1", state)

    assert resolve_note_reload("paper-1", state, discard=False) is True

    assert state[note_draft_key("paper-1")] == "exact unsaved draft"
    assert pending_note_discard_reload_key("paper-1") not in state
    assert pending_note_reload_key("paper-1") not in state


def test_clean_reload_is_idempotent_across_reruns() -> None:
    state = {
        note_draft_key("paper-1"): "clean",
        note_baseline_key("paper-1"): "clean",
    }
    assert request_note_reload("paper-1", state) == "queued"

    assert apply_queued_reload("paper-1", state, "disk replacement") is True
    assert apply_queued_reload("paper-1", state, "later disk text") is False

    assert state[note_draft_key("paper-1")] == "disk replacement"
    assert state[note_baseline_key("paper-1")] == "disk replacement"


def test_text_replacement_precedes_append_and_is_applied_once() -> None:
    state = {
        note_draft_key("paper-1"): "original",
        note_baseline_key("paper-1"): "original",
    }
    queue_note_text_replacement("paper-1", state, "replacement")
    state[pending_note_block_append_key("paper-1")] = "append"

    first = apply_queued_content_updates("paper-1", state, lambda draft, addition: f"{draft}+{addition}")
    second = apply_queued_content_updates("paper-1", state, lambda draft, addition: f"{draft}+{addition}")

    assert first == second == "replacement+append"
    assert pending_note_text_update_key("paper-1") not in state
    assert pending_note_block_append_key("paper-1") not in state


def test_queued_text_replacement_does_not_overwrite_newer_edit() -> None:
    state = {
        note_draft_key("paper-1"): "source draft",
        note_baseline_key("paper-1"): "saved",
    }
    queue_note_text_replacement("paper-1", state, "queued replacement")
    state[note_draft_key("paper-1")] = "newer exact edit"

    result = apply_queued_content_updates("paper-1", state, lambda draft, addition: draft + addition)

    assert result == "newer exact edit"
    assert state[note_draft_key("paper-1")] == "newer exact edit"
    assert pending_note_text_update_key("paper-1") not in state


def test_state_and_pending_events_are_isolated_by_paper_id() -> None:
    state = {}
    initialize_reader_note_state("paper-1", state, "paper one")
    initialize_reader_note_state("paper-2", state, "paper two")
    state[note_draft_key("paper-1")] = "paper one edited"

    request_note_reload("paper-1", state)

    assert derive_reader_note_state("paper-1", state).dirty is True
    assert derive_reader_note_state("paper-2", state).dirty is False
    assert pending_note_discard_reload_key("paper-1") in state
    assert pending_note_discard_reload_key("paper-2") not in state
    assert state[note_draft_key("paper-2")] == "paper two"
