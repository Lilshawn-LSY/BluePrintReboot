from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_script(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_windows_dev_script_files_exist() -> None:
    for relative_path in (
        "scripts/dev_setup.ps1",
        "scripts/dev_check.ps1",
        "scripts/run_app.ps1",
        "start_blueprint.bat",
    ):
        assert (PROJECT_ROOT / relative_path).is_file()


def test_dev_check_runs_smoke_check_and_pytest() -> None:
    script = read_script("scripts/dev_check.ps1")

    assert "scripts/smoke_check.py" in script
    assert "pytest" in script


def test_run_app_launches_streamlit_entrypoint_with_port() -> None:
    script = read_script("scripts/run_app.ps1")

    assert "streamlit" in script
    assert "app.py" in script
    assert "$Port" in script
    assert "--server.port" in script


def test_dev_setup_uses_venv_and_requirements() -> None:
    script = read_script("scripts/dev_setup.ps1")

    assert ".venv" in script
    assert "requirements.txt" in script


def test_bootstrap_scripts_do_not_contain_obviously_dangerous_commands() -> None:
    script_text = "\n".join(
        read_script(relative_path)
        for relative_path in (
            "scripts/dev_setup.ps1",
            "scripts/dev_check.ps1",
            "scripts/run_app.ps1",
            "start_blueprint.bat",
        )
    ).lower()

    dangerous_commands = (
        "remove-item -recurse papers",
        "remove-item -recurse notes",
        "remove-item -recurse data",
        "git reset --hard",
        "git clean -fd",
        "del /s papers",
        "rmdir /s papers",
    )

    for command in dangerous_commands:
        assert command not in script_text
