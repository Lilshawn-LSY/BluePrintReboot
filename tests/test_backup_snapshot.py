import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from config.contact import APP_VERSION
from services.backup_snapshot import create_backup_snapshot, verify_backup_snapshot
from tests.helpers import make_workspace


def _seed_workspace(name: str) -> Path:
    workspace = make_workspace(name)
    (workspace / "data" / "projects").mkdir(parents=True)
    (workspace / "data" / "note_blocks").mkdir(parents=True)
    (workspace / "notes").mkdir()
    (workspace / "papers").mkdir()
    (workspace / "config").mkdir()
    (workspace / "config" / "tag_book").mkdir()
    (workspace / ".streamlit").mkdir()
    (workspace / "data" / "paper_index.csv").write_text(
        "paper_id,filename,filepath,title,authors,year\npaper-1,Paper.pdf,Paper.pdf,Paper,Author,2024\n",
        encoding="utf-8",
    )
    (workspace / "data" / "note_imports.json").write_text("[]", encoding="utf-8")
    (workspace / "data" / "projects" / "projects.json").write_text(
        json.dumps([{"id": "project-1"}]), encoding="utf-8"
    )
    (workspace / "data" / "projects" / "project_links.json").write_text(
        json.dumps([{"id": "link-1"}]), encoding="utf-8"
    )
    (workspace / "data" / "note_blocks" / "paper-1.json").write_text("[]", encoding="utf-8")
    (workspace / "notes" / "paper-1.md").write_text("# Note", encoding="utf-8")
    (workspace / "config" / "tag_rules.json").write_text("[]", encoding="utf-8")
    (workspace / "config" / "canonical_tags.json").write_text("[]", encoding="utf-8")
    for filename in (
        "tag_book.json",
        "method_lexicon.json",
        "normalization_rules.json",
        "blocked_terms.json",
        "candidate_patterns.json",
    ):
        (workspace / "config" / "tag_book" / filename).write_text("{}", encoding="utf-8")
    (workspace / ".streamlit" / "config.toml").write_text("[theme]", encoding="utf-8")
    (workspace / "papers" / "Paper.pdf").write_bytes(b"%PDF-1.4\ncontent")
    return workspace


def test_light_snapshot_and_manifest_are_created_without_pdfs() -> None:
    workspace = _seed_workspace("backup-light")
    exports_dir = workspace / "exports"
    fixed_time = datetime(2026, 6, 21, 12, 30, tzinfo=timezone.utc)

    result = create_backup_snapshot(
        project_root=workspace,
        exports_dir=exports_dir,
        include_pdfs=False,
        now=fixed_time,
    )

    snapshot_path = Path(result["snapshot_path"])
    assert snapshot_path.name == "blueprint_snapshot_20260621T123000Z_light.zip"
    assert snapshot_path.exists()
    with ZipFile(snapshot_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
    assert "data/paper_index.csv" in names
    assert "data/note_imports.json" in names
    assert "data/projects/projects.json" in names
    assert "data/projects/project_links.json" in names
    assert "data/note_blocks/paper-1.json" in names
    assert "notes/paper-1.md" in names
    assert "config/tag_rules.json" in names
    assert "config/canonical_tags.json" in names
    assert "config/tag_book/tag_book.json" in names
    assert "config/tag_book/method_lexicon.json" in names
    assert "config/tag_book/normalization_rules.json" in names
    assert "config/tag_book/blocked_terms.json" in names
    assert "config/tag_book/candidate_patterns.json" in names
    assert ".streamlit/config.toml" in names
    assert "papers/Paper.pdf" not in names
    assert manifest["app_version"] == APP_VERSION
    assert manifest["snapshot_type"] == "light"
    assert manifest["includes_pdfs"] is False
    assert manifest["policy"]["purpose"] == "Backup private local library data. Source code remains in GitHub."
    assert manifest["policy"]["extracted_text_cache"]["included"] is False
    assert "data/extracted_text/" in manifest["policy"]["excluded_by_default"]
    assert manifest["counts"]["index_rows"] == 1
    assert manifest["counts"]["projects"] == 1
    assert manifest["counts"]["project_links"] == 1
    assert manifest["counts"]["notes"] == 1
    assert manifest["counts"]["pdfs"] == 0
    assert all({"path", "size_bytes", "sha256"} <= set(item) for item in manifest["included_files"])


def test_full_snapshot_includes_pdfs() -> None:
    workspace = _seed_workspace("backup-full")

    result = create_backup_snapshot(
        project_root=workspace,
        exports_dir=workspace / "exports",
        include_pdfs=True,
        now=datetime(2026, 6, 21, 12, 31, tzinfo=timezone.utc),
    )

    with ZipFile(result["snapshot_path"]) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
    assert "papers/Paper.pdf" in names
    assert manifest["snapshot_type"] == "full"
    assert manifest["includes_pdfs"] is True
    assert manifest["counts"]["pdfs"] == 1


def test_snapshot_excludes_ignored_directories() -> None:
    workspace = _seed_workspace("backup-ignored")
    ignored_files = [
        workspace / ".venv" / "secret.txt",
        workspace / ".pytest_cache" / "cache.txt",
        workspace / ".git" / "config",
        workspace / "node_modules" / "package-cache.txt",
        workspace / ".cache" / "package-cache.txt",
        workspace / "notes" / "__pycache__" / "note.md",
        workspace / "data" / "projects" / ".venv" / "nested.json",
        workspace / "data" / "extracted_text" / "paper-1.txt",
        workspace / "data" / "extracted_text" / "paper-1.json",
        workspace / "data" / "paper_profiles" / "paper-1.json",
        workspace / "notes" / "debug.log",
        workspace / ".streamlit" / "secrets.toml",
    ]
    for path in ignored_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("exclude", encoding="utf-8")

    result = create_backup_snapshot(
        project_root=workspace,
        exports_dir=workspace / "exports",
        include_pdfs=True,
    )

    with ZipFile(result["snapshot_path"]) as archive:
        names = archive.namelist()
    assert not any(
        ignored in name.split("/")
        for name in names
        for ignored in (".venv", ".pytest_cache", ".git", "__pycache__", "node_modules", ".cache")
    )
    assert "data/extracted_text/paper-1.txt" not in names
    assert "data/extracted_text/paper-1.json" not in names
    assert "data/paper_profiles/paper-1.json" not in names
    assert "notes/debug.log" not in names
    assert ".streamlit/secrets.toml" not in names


def test_snapshot_verifier_accepts_created_snapshot_without_extracting() -> None:
    workspace = _seed_workspace("backup-verify-success")
    result = create_backup_snapshot(
        project_root=workspace,
        exports_dir=workspace / "exports",
        include_pdfs=True,
    )

    verification = verify_backup_snapshot(result["snapshot_path"])

    assert verification["valid"] is True
    assert verification["errors"] == []
    assert verification["checked_files"] == result["manifest"]["counts"]["included_files"]
    assert not (workspace / "restored").exists()


def test_snapshot_verifier_rejects_unsafe_missing_and_unlisted_paths() -> None:
    workspace = make_workspace("backup-verify-paths")
    snapshot_path = workspace / "unsafe.zip"
    manifest = {
        "snapshot_type": "light",
        "includes_pdfs": False,
        "included_files": [
            {"path": "../outside.txt", "size_bytes": 1, "sha256": "0" * 64},
            {"path": "notes/missing.md", "size_bytes": 1, "sha256": "0" * 64},
        ],
        "counts": {
            "included_files": 2,
            "index_rows": 0,
            "projects": 0,
            "project_links": 0,
            "notes": 1,
            "note_block_files": 0,
            "pdfs": 0,
        },
    }
    with ZipFile(snapshot_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("notes/unlisted.md", "extra")

    verification = verify_backup_snapshot(snapshot_path)

    assert verification["valid"] is False
    assert any("unsafe" in error for error in verification["errors"])
    assert any("missing" in error for error in verification["errors"])
    assert any("unlisted" in error for error in verification["errors"])


def test_snapshot_verifier_rejects_content_and_count_mismatches() -> None:
    workspace = _seed_workspace("backup-verify-content")
    created = create_backup_snapshot(
        project_root=workspace,
        exports_dir=workspace / "exports",
        include_pdfs=False,
    )
    source_path = Path(created["snapshot_path"])
    broken_path = workspace / "broken.zip"
    with ZipFile(source_path) as source:
        manifest = json.loads(source.read("manifest.json"))
        members = {name: source.read(name) for name in source.namelist() if name != "manifest.json"}
    manifest["snapshot_type"] = "full"
    manifest["counts"]["notes"] = 99
    note_entry = next(item for item in manifest["included_files"] if item["path"].startswith("notes/"))
    note_entry["size_bytes"] += 1
    note_entry["sha256"] = "0" * 64
    with ZipFile(broken_path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
        archive.writestr("manifest.json", json.dumps(manifest))

    verification = verify_backup_snapshot(broken_path)

    assert verification["valid"] is False
    assert any("snapshot_type and includes_pdfs" in error for error in verification["errors"])
    assert any("size_bytes mismatch" in error for error in verification["errors"])
    assert any("sha256 mismatch" in error for error in verification["errors"])
    assert any("counts.notes mismatch" in error for error in verification["errors"])
