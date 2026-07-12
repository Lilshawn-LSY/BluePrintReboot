import hashlib
import json
from datetime import datetime, timezone

import pytest

from services.storage_recovery import (
    StorageRecoveryError,
    export_recovery_copy,
    quarantine_file,
    restore_quarantined_file,
)
from tests.helpers import make_workspace


NOW = datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc)


def _source(name: str = "recovery"):
    root = make_workspace(name)
    source = root / "data" / "extracted_text" / "paper.txt"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"\x00corrupt\xffbytes")
    return root, source


def test_recovery_copy_preserves_exact_bytes_and_manifest() -> None:
    root, source = _source("recovery-exact")
    before = source.read_bytes()
    result = export_recovery_copy(source, workspace_root=root, recovery_dir=root / "exports" / "recovery", storage_class="rebuildable cache", reason="invalid UTF-8", now=NOW)

    copy = type(source)(result["copy_path"])
    manifest = json.loads(type(source)(result["manifest_path"]).read_text(encoding="utf-8"))
    assert copy.read_bytes() == before == source.read_bytes()
    assert manifest["byte_size"] == len(before)
    assert manifest["sha256"] == hashlib.sha256(before).hexdigest()
    assert manifest["workspace_relative_path"] == "data/extracted_text/paper.txt"


def test_recovery_copy_collision_is_safe() -> None:
    root, source = _source("recovery-collision")
    first = export_recovery_copy(source, workspace_root=root, recovery_dir=root / "exports", storage_class="rebuildable cache", reason="test", now=NOW)
    second = export_recovery_copy(source, workspace_root=root, recovery_dir=root / "exports", storage_class="rebuildable cache", reason="test", now=NOW)
    assert first["copy_path"] != second["copy_path"]


def test_recovery_rejects_outside_workspace() -> None:
    root, _source_path = _source("recovery-contained")
    outside = root.parent / "outside.bin"
    outside.write_bytes(b"outside")
    with pytest.raises(StorageRecoveryError, match="workspace"):
        export_recovery_copy(outside, workspace_root=root, recovery_dir=root / "exports", storage_class="critical user state", reason="test")


def test_recovery_rejects_output_outside_workspace() -> None:
    root, source = _source("recovery-output-contained")
    with pytest.raises(StorageRecoveryError, match="output"):
        export_recovery_copy(source, workspace_root=root, recovery_dir=root.parent / "external-recovery", storage_class="rebuildable cache", reason="test")


def test_quarantine_requires_rebuildable_and_confirmation() -> None:
    root, source = _source("quarantine-eligibility")
    with pytest.raises(StorageRecoveryError, match="confirmation"):
        quarantine_file(source, workspace_root=root, quarantine_dir=root / "quarantine", storage_class="rebuildable cache", reason="test", rebuildable=True, confirm=False)
    with pytest.raises(StorageRecoveryError, match="rebuildable"):
        quarantine_file(source, workspace_root=root, quarantine_dir=root / "quarantine", storage_class="critical user state", reason="test", rebuildable=False, confirm=True)
    assert source.exists()


def test_quarantine_and_verified_restore_round_trip() -> None:
    root, source = _source("quarantine-restore")
    before = source.read_bytes()
    quarantined = quarantine_file(source, workspace_root=root, quarantine_dir=root / "quarantine", storage_class="rebuildable cache", reason="test", rebuildable=True, confirm=True, now=NOW)
    assert not source.exists()
    assert quarantine_file(source, workspace_root=root, quarantine_dir=root / "quarantine", storage_class="rebuildable cache", reason="test", rebuildable=True, confirm=True)["status"] == "already_absent"

    restored = restore_quarantined_file(quarantined["manifest_path"], workspace_root=root, confirm=True)
    assert restored["status"] == "restored"
    assert source.read_bytes() == before
    assert type(source)(quarantined["copy_path"]).exists()


def test_restore_conflict_and_tampering_preserve_destination() -> None:
    root, source = _source("restore-conflict")
    quarantined = quarantine_file(source, workspace_root=root, quarantine_dir=root / "quarantine", storage_class="rebuildable cache", reason="test", rebuildable=True, confirm=True)
    source.write_bytes(b"new active bytes")
    with pytest.raises(StorageRecoveryError, match="conflict"):
        restore_quarantined_file(quarantined["manifest_path"], workspace_root=root, confirm=True)
    assert source.read_bytes() == b"new active bytes"
    source.unlink()
    type(source)(quarantined["copy_path"]).write_bytes(b"tampered")
    with pytest.raises(StorageRecoveryError, match="match"):
        restore_quarantined_file(quarantined["manifest_path"], workspace_root=root, confirm=True)
    assert not source.exists()


def test_failed_quarantine_copy_preserves_source(monkeypatch) -> None:
    root, source = _source("quarantine-copy-failure")
    before = source.read_bytes()
    monkeypatch.setattr("services.storage_recovery.shutil.copyfileobj", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy failed")))
    with pytest.raises(OSError, match="copy failed"):
        quarantine_file(source, workspace_root=root, quarantine_dir=root / "quarantine", storage_class="rebuildable cache", reason="test", rebuildable=True, confirm=True)
    assert source.read_bytes() == before


def test_restore_rejects_nonmatching_external_manifest() -> None:
    root, source = _source("restore-manifest-contained")
    external_copy = root.parent / "external-quarantine.bin"
    external_copy.write_bytes(source.read_bytes())
    manifest = root / "data" / "quarantine" / "crafted.manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"original_path": str(source), "copy_path": str(external_copy), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "byte_size": source.stat().st_size}), encoding="utf-8")
    source.unlink()
    with pytest.raises(StorageRecoveryError, match="workspace-owned"):
        restore_quarantined_file(manifest, workspace_root=root, confirm=True)
    assert not source.exists()
