import subprocess
from pathlib import Path

from scripts.check_repo_hygiene import (
    ALLOWED_PRIVATE_PLACEHOLDERS,
    PROJECT_ROOT,
    check_repository,
    inspect_tracked_entries,
    main,
)


def reasons_for(*entries: str) -> dict[str, str]:
    return {violation.path: violation.reason for violation in inspect_tracked_entries(entries)}


def test_current_repository_passes_tracked_file_hygiene() -> None:
    entries, violations = check_repository(PROJECT_ROOT)

    assert entries
    assert violations == []


def test_exact_accidental_filename_is_rejected() -> None:
    violations = reasons_for("tatus --short")

    assert violations == {"tatus --short": "known accidental command-output artifact"}


def test_root_logs_shell_fragments_and_generated_evidence_are_rejected() -> None:
    violations = reasons_for(
        "terminal.log",
        "git status --short.txt",
        "validation-summary.json",
        "docs/pytest-results.txt",
    )

    assert "root log/output" in violations["terminal.log"]
    assert "shell flag or command fragment" in violations["git status --short.txt"]
    assert "ignored artifacts/" in violations["validation-summary.json"]
    assert "ignored artifacts/" in violations["docs/pytest-results.txt"]


def test_private_runtime_paths_are_rejected_without_scanning_contents() -> None:
    violations = reasons_for(
        "artifacts/tracker_status.csv",
        "data/paper_index.csv",
        "notes/private.md",
        "papers/private.pdf",
        "exports/snapshot.zip",
        ".streamlit/secrets.toml",
        "tests/_tmp/result.txt",
        "frontend/node_modules/package/index.js",
    )

    assert set(violations) == {
        "artifacts/tracker_status.csv",
        "data/paper_index.csv",
        "notes/private.md",
        "papers/private.pdf",
        "exports/snapshot.zip",
        ".streamlit/secrets.toml",
        "tests/_tmp/result.txt",
        "frontend/node_modules/package/index.js",
    }


def test_private_directory_placeholders_and_legitimate_roots_are_allowed() -> None:
    entries = [*sorted(ALLOWED_PRIVATE_PLACEHOLDERS), "README.md", "docs/ROADMAP.md", "services/note_import.py"]

    assert inspect_tracked_entries(entries) == []


def test_disposable_git_repository_detects_reintroduced_artifact(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    (repository / "README.md").write_text("fixture\n", encoding="utf-8")
    (repository / "tatus --short").write_text("console output\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "README.md", "tatus --short"], check=True)

    entries, violations = check_repository(repository)

    assert "tatus --short" in entries
    assert [violation.path for violation in violations] == ["tatus --short"]


def test_hygiene_cli_reports_clear_failure(tmp_path: Path, capsys) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    (repository / "terminal.log").write_text("output\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "terminal.log"], check=True)

    assert main(["--project-root", str(repository)]) == 1
    output = capsys.readouterr().out
    assert "Repository hygiene check failed" in output
    assert "terminal.log" in output
    assert "root log/output artifact" in output
