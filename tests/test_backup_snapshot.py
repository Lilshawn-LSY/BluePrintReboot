import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from services.backup_snapshot import create_backup_snapshot
from tests.helpers import make_workspace


def _seed_workspace(name: str) -> Path:
    workspace = make_workspace(name)
    (workspace / "data" / "projects").mkdir(parents=True)
    (workspace / "data" / "note_blocks").mkdir(parents=True)
    (workspace / "notes").mkdir()
    (workspace / "papers").mkdir()
    (workspace / "config").mkdir()
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
    assert ".streamlit/config.toml" in names
    assert "papers/Paper.pdf" not in names
    assert manifest["app_version"] == "1.0.10"
    assert manifest["snapshot_type"] == "light"
    assert manifest["includes_pdfs"] is False
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
        workspace / "notes" / "__pycache__" / "note.md",
        workspace / "data" / "projects" / ".venv" / "nested.json",
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
        for ignored in (".venv", ".pytest_cache", ".git", "__pycache__")
    )
