import hashlib

from services.lifecycle_decisions import ignore_exact_duplicate, is_exact_duplicate_ignored, load_duplicate_decisions, unignore_exact_duplicate
from tests.helpers import make_workspace


def test_exact_duplicate_ignore_is_path_and_hash_bound_and_reversible() -> None:
    root = make_workspace("duplicate-decision")
    first = root / "papers" / "first.pdf"
    second = root / "papers" / "second.pdf"
    first.parent.mkdir()
    first.write_bytes(b"same")
    second.write_bytes(b"same")
    digest = hashlib.sha256(b"same").hexdigest()
    store = root / "data" / "lifecycle_decisions.json"

    ignore_exact_duplicate(first, digest, size_bytes=4, modified_at="now", decision_path=store, workspace_root=root)
    assert is_exact_duplicate_ignored(first, digest, decision_path=store, workspace_root=root)
    assert not is_exact_duplicate_ignored(first, hashlib.sha256(b"changed").hexdigest(), decision_path=store, workspace_root=root)
    assert not is_exact_duplicate_ignored(second, digest, decision_path=store, workspace_root=root)
    assert unignore_exact_duplicate(first, decision_path=store, workspace_root=root)
    assert not is_exact_duplicate_ignored(first, digest, decision_path=store, workspace_root=root)


def test_duplicate_decision_store_write_uses_atomic_json(monkeypatch) -> None:
    root = make_workspace("duplicate-decision-atomic")
    pdf = root / "papers" / "paper.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"same")
    store = root / "data" / "lifecycle_decisions.json"
    calls = []
    from services import lifecycle_decisions
    real_write = lifecycle_decisions.atomic_write_json
    monkeypatch.setattr(lifecycle_decisions, "atomic_write_json", lambda *args, **kwargs: (calls.append(args[0]), real_write(*args, **kwargs))[1])
    ignore_exact_duplicate(pdf, hashlib.sha256(b"same").hexdigest(), size_bytes=4, modified_at="now", decision_path=store, workspace_root=root)
    assert calls == [store]
    assert len(load_duplicate_decisions(store)) == 1
