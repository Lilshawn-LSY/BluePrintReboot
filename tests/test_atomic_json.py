import json
from pathlib import Path

import pytest

from storage.atomic_json import CorruptJsonError, atomic_write_json, read_json_file
from tests.helpers import make_workspace


def test_atomic_write_json_flushes_fsyncs_and_replaces_from_same_directory(monkeypatch) -> None:
    workspace = make_workspace("atomic-json-helper")
    target = workspace / "store.json"
    original_replace = __import__("os").replace
    fsync_calls: list[int] = []
    replace_calls: list[tuple[Path, Path]] = []

    def spy_replace(source, destination) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        replace_calls.append((source_path, destination_path))
        assert source_path.parent.resolve() == destination_path.parent.resolve()
        original_replace(source_path, destination_path)

    monkeypatch.setattr("storage.atomic_json.os.fsync", lambda fileno: fsync_calls.append(fileno))
    monkeypatch.setattr("storage.atomic_json.os.replace", spy_replace)

    atomic_write_json(target, {"answer": 42}, indent=2, ensure_ascii=False, trailing_newline=True)

    assert json.loads(target.read_text(encoding="utf-8")) == {"answer": 42}
    assert target.read_text(encoding="utf-8").endswith("\n")
    assert fsync_calls
    assert replace_calls == [(replace_calls[0][0], target)]
    assert sorted(path.name for path in workspace.iterdir()) == ["store.json"]


def test_atomic_write_json_serialization_failure_leaves_existing_file() -> None:
    workspace = make_workspace("atomic-json-serialization")
    target = workspace / "store.json"
    atomic_write_json(target, {"safe": True})
    before = target.read_bytes()

    with pytest.raises(TypeError):
        atomic_write_json(target, {"unsafe": object()})

    assert target.read_bytes() == before
    assert sorted(path.name for path in workspace.iterdir()) == ["store.json"]


def test_read_json_file_raises_typed_corrupt_json_error() -> None:
    workspace = make_workspace("atomic-json-corrupt")
    target = workspace / "store.json"
    target.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CorruptJsonError) as error:
        read_json_file(target, store_name="Test store")

    assert error.value.path == target
    assert "Test store is invalid JSON" in error.value.summary
    assert "Do not overwrite" in error.value.suggested_action
