from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from services import note_block_commands
from services.note_block_commands import (
    NoteBlockCommandConflict,
    NoteBlockCommandInvalid,
    NoteBlockCommandNotFound,
    NoteBlockCommandService,
    NoteBlockCommandUnavailable,
)
from services.note_block_read_model import note_blocks_revision
from storage import note_block_store
from storage.note_block_store import list_note_blocks, note_blocks_path
from storage.workspace_lock import WorkspaceLockUnavailable


def _service(tmp_path: Path) -> NoteBlockCommandService:
    index_csv = tmp_path / "data" / "paper_index.csv"
    index_csv.parent.mkdir(parents=True)
    pd.DataFrame([{"paper_id": "paper-1", "title": "Paper"}]).to_csv(index_csv, index=False)
    return NoteBlockCommandService(
        note_blocks_dir=tmp_path / "data" / "note_blocks",
        index_csv=index_csv,
    )


def _content(**updates: object) -> dict[str, object]:
    return {
        "block_type": "summary",
        "title": "Title",
        "text": "Text",
        "page": "1",
        "figure": "Figure 1",
        "quote": "Quote",
        "tags": ["one"],
        **updates,
    }


def _evidence(path: Path) -> tuple[bytes, int]:
    return path.read_bytes(), path.stat().st_mtime_ns


def test_create_and_update_every_allowlisted_field(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_note_block(
        "paper-1",
        _content(),
        note_blocks_revision("paper-1", []),
    )
    updated = service.update_note_block(
        "paper-1",
        created.block["id"],
        _content(
            block_type="limitation",
            title="Updated",
            text="Updated text",
            page="2",
            figure="Figure 2",
            quote="Updated quote",
            tags=["two", "three"],
        ),
        created.note_blocks_revision,
    )

    assert created.status == "created"
    assert updated.status == "saved"
    assert {field: updated.block[field] for field in _content()} == _content(
        block_type="limitation",
        title="Updated",
        text="Updated text",
        page="2",
        figure="Figure 2",
        quote="Updated quote",
        tags=["two", "three"],
    )
    assert updated.block["id"] == created.block["id"]
    assert updated.block["paper_id"] == "paper-1"
    assert updated.block["created_at"] == created.block["created_at"]


def test_exact_no_op_does_not_rewrite_file(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_note_block("paper-1", _content(), note_blocks_revision("paper-1", []))
    path = note_blocks_path("paper-1", service.note_blocks_dir)
    before = _evidence(path)

    result = service.update_note_block(
        "paper-1",
        created.block["id"],
        {"text": "Text"},
        created.note_blocks_revision,
    )

    assert result.status == "no_op"
    assert _evidence(path) == before


def test_stale_revision_and_unknown_identity_have_zero_mutation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_note_block("paper-1", _content(), note_blocks_revision("paper-1", []))
    path = note_blocks_path("paper-1", service.note_blocks_dir)
    before = _evidence(path)

    with pytest.raises(NoteBlockCommandConflict):
        service.update_note_block("paper-1", created.block["id"], {"text": "stale"}, "0" * 64)
    with pytest.raises(NoteBlockCommandNotFound):
        service.update_note_block("paper-1", "missing", {"text": "missing"}, created.note_blocks_revision)
    with pytest.raises(NoteBlockCommandNotFound):
        service.create_note_block("missing", _content(), note_blocks_revision("missing", []))

    assert _evidence(path) == before


def test_persistence_failure_restores_exact_bytes_and_timestamp(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path)
    created = service.create_note_block("paper-1", _content(), note_blocks_revision("paper-1", []))
    path = note_blocks_path("paper-1", service.note_blocks_dir)
    before = _evidence(path)

    def write_then_fail(_paper_id, _blocks, base_dir):
        note_blocks_path("paper-1", base_dir).write_text('[{"private":"intermediate"}]', encoding="utf-8")
        raise OSError("private persistence failure")

    monkeypatch.setattr(note_block_store, "save_note_blocks", write_then_fail)
    with pytest.raises(NoteBlockCommandUnavailable):
        service.update_note_block(
            "paper-1",
            created.block["id"],
            {"text": "new"},
            created.note_blocks_revision,
        )

    assert _evidence(path) == before
    assert list_note_blocks("paper-1", service.note_blocks_dir)[0]["text"] == "Text"


def test_post_write_verification_failure_rolls_back_new_file(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path)
    path = note_blocks_path("paper-1", service.note_blocks_dir)
    original = note_block_store.save_note_blocks

    def persist_different(paper_id, blocks, base_dir):
        different = [{**block, "text": "different"} for block in blocks]
        return original(paper_id, different, base_dir)

    monkeypatch.setattr(note_block_store, "save_note_blocks", persist_different)
    with pytest.raises(NoteBlockCommandUnavailable):
        service.create_note_block("paper-1", _content(), note_blocks_revision("paper-1", []))

    assert not path.exists()


def test_workspace_lock_failure_is_private_safe_and_non_mutating(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path)

    @contextmanager
    def unavailable(_root):
        raise WorkspaceLockUnavailable("C:/private/workspace")
        yield

    monkeypatch.setattr(note_block_commands, "workspace_write_lock", unavailable)

    with pytest.raises(NoteBlockCommandUnavailable) as error:
        service.create_note_block("paper-1", _content(), note_blocks_revision("paper-1", []))
    assert str(error.value) == ""
    assert not note_blocks_path("paper-1", service.note_blocks_dir).exists()


@pytest.mark.parametrize(
    "content",
    [
        _content(block_type="unsupported"),
        {**_content(), "id": "client-owned"},
        _content(title="x" * 1_001),
        _content(tags=[f"tag-{index}" for index in range(26)]),
        _content(tags=["x" * 101]),
        _content(tags=[1]),
    ],
)
def test_invalid_type_unsupported_identity_and_bounds_have_zero_mutation(
    tmp_path: Path,
    content: dict[str, object],
) -> None:
    service = _service(tmp_path)

    with pytest.raises(NoteBlockCommandInvalid):
        service.create_note_block(
            "paper-1",
            content,
            note_blocks_revision("paper-1", []),
        )

    assert not note_blocks_path("paper-1", service.note_blocks_dir).exists()


def test_update_rejects_every_server_owned_field(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_note_block(
        "paper-1",
        _content(),
        note_blocks_revision("paper-1", []),
    )
    path = note_blocks_path("paper-1", service.note_blocks_dir)
    before = _evidence(path)

    for field in ("id", "paper_id", "created_at", "updated_at"):
        with pytest.raises(NoteBlockCommandInvalid):
            service.update_note_block(
                "paper-1",
                created.block["id"],
                {field: "client-owned"},
                created.note_blocks_revision,
            )

    assert _evidence(path) == before


def test_collection_count_bound_prevents_create_without_rewrite(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    created = service.create_note_block(
        "paper-1",
        _content(),
        note_blocks_revision("paper-1", []),
    )
    path = note_blocks_path("paper-1", service.note_blocks_dir)
    before = _evidence(path)
    monkeypatch.setattr(note_block_commands, "MAX_NOTE_BLOCKS_PER_PAPER", 1)

    with pytest.raises(NoteBlockCommandInvalid):
        service.create_note_block(
            "paper-1",
            _content(title="Second"),
            created.note_blocks_revision,
        )

    assert _evidence(path) == before


def test_state_is_reloaded_after_lock_before_revision_comparison(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    external = {
        "id": "external-block",
        "paper_id": "paper-1",
        **_content(title="Concurrent"),
        "created_at": "2026-08-02T00:00:00+00:00",
        "updated_at": "2026-08-02T00:00:00+00:00",
    }

    @contextmanager
    def concurrent_write(_root):
        note_block_store.save_note_blocks("paper-1", [external], service.note_blocks_dir)
        yield

    monkeypatch.setattr(note_block_commands, "workspace_write_lock", concurrent_write)
    with pytest.raises(NoteBlockCommandConflict):
        service.create_note_block(
            "paper-1",
            _content(),
            note_blocks_revision("paper-1", []),
        )

    assert [block["id"] for block in service._load("paper-1")] == ["external-block"]


@pytest.mark.parametrize("failure", [TypeError("serialization"), OSError("replace")])
def test_serialization_and_atomic_replace_failures_do_not_create_a_file(
    tmp_path: Path,
    monkeypatch,
    failure: Exception,
) -> None:
    service = _service(tmp_path)

    def fail_save(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(note_block_store, "save_note_blocks", fail_save)
    with pytest.raises(NoteBlockCommandUnavailable) as error:
        service.create_note_block(
            "paper-1",
            _content(),
            note_blocks_revision("paper-1", []),
        )

    assert str(error.value) == ""
    assert not note_blocks_path("paper-1", service.note_blocks_dir).exists()
