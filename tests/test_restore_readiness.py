from datetime import datetime, timezone
from pathlib import Path

from services.backup_snapshot import create_backup_snapshot
from services.restore_readiness import check_disposable_restore_target
from tests.helpers import make_workspace


def _snapshot(name: str):
    base = make_workspace(name)
    protected = base / "active-repository"
    protected.mkdir()
    (protected / "data").mkdir()
    (protected / "data" / "paper_index.csv").write_text("paper_id,filename\n", encoding="utf-8")
    snapshot = create_backup_snapshot(project_root=protected, exports_dir=base / "snapshots", now=datetime(2026, 7, 12, tzinfo=timezone.utc))["snapshot_path"]
    target = base / "disposable-target"
    target.mkdir()
    return base, protected, Path(snapshot), target


def test_restore_readiness_accepts_verified_snapshot_and_empty_external_target_without_writes() -> None:
    _base, protected, snapshot, target = _snapshot("restore-ready")
    before = snapshot.read_bytes()
    result = check_disposable_restore_target(snapshot, target, protected_root=protected)
    assert result["ready"] is True
    assert result["read_only"] is True
    assert result["target_empty"] is True
    assert list(target.iterdir()) == []
    assert snapshot.read_bytes() == before


def test_restore_readiness_rejects_nonempty_missing_and_protected_targets() -> None:
    base, protected, snapshot, target = _snapshot("restore-reject")
    (target / "conflict.txt").write_text("keep", encoding="utf-8")
    nonempty = check_disposable_restore_target(snapshot, target, protected_root=protected)
    missing = check_disposable_restore_target(snapshot, base / "not-created", protected_root=protected)
    active = check_disposable_restore_target(snapshot, protected, protected_root=protected)
    assert nonempty["ready"] is False and "empty" in " ".join(nonempty["errors"]).lower()
    assert missing["ready"] is False and "already exist" in " ".join(missing["errors"]).lower()
    assert active["ready"] is False and "active repository" in " ".join(active["errors"]).lower()


def test_restore_readiness_rejects_invalid_snapshot_and_keeps_target_empty() -> None:
    base, protected, _snapshot_path, target = _snapshot("restore-invalid")
    invalid = base / "invalid.zip"
    invalid.write_bytes(b"not a zip")
    result = check_disposable_restore_target(invalid, target, protected_root=protected)
    assert result["ready"] is False
    assert result["snapshot_valid"] is False
    assert list(target.iterdir()) == []
