from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_script(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_windows_dev_script_files_exist() -> None:
    for relative_path in (
        "scripts/dev_setup.ps1",
        "scripts/frontend_setup.ps1",
        "scripts/dev_check.ps1",
        "scripts/resolve_node.ps1",
        "scripts/run_app.ps1",
        "scripts/run_api.ps1",
        "scripts/run_frontend.ps1",
        "scripts/restore_check.py",
        "start_blueprint.bat",
    ):
        assert (PROJECT_ROOT / relative_path).is_file()


def test_dev_check_runs_smoke_check_and_pytest() -> None:
    script = read_script("scripts/dev_check.ps1")

    assert "scripts/smoke_check.py" in script
    assert "pytest" in script
    assert '"npm run lint"' in script
    assert '"npm test"' in script
    assert "$PythonOnly" in script
    assert "PARTIAL VALIDATION" in script
    assert "$WriteEvidence" in script
    assert "validation-summary.json" in script


def test_node_resolver_has_required_priority_and_minimum() -> None:
    script = read_script("scripts/resolve_node.ps1")

    explicit_position = script.index("$NodeHome")
    environment_position = script.index("$env:BLUEPRINT_NODE_HOME")
    path_position = script.index("Get-Command node.exe")
    assert explicit_position < environment_position < path_position
    assert '22.13.0' in script
    assert 'node.exe' in script
    assert 'npm.cmd' in script
    assert 'SetEnvironmentVariable' not in script


def test_frontend_setup_is_lockfile_deterministic() -> None:
    script = read_script("scripts/frontend_setup.ps1")

    assert "package-lock.json" in script
    assert '@("ci")' in script
    assert "npm install" not in script.lower()


def test_run_app_launches_streamlit_entrypoint_with_port() -> None:
    script = read_script("scripts/run_app.ps1")

    assert "streamlit" in script
    assert "app.py" in script
    assert "$Port" in script
    assert "--server.port" in script


def test_run_api_launches_local_read_only_entrypoint() -> None:
    script = read_script("scripts/run_api.ps1")

    assert ".venv" in script
    assert "api.main:app" in script
    assert "127.0.0.1" in script
    assert "uvicorn" in script
    assert "$Port" in script


def test_run_frontend_launches_local_application_shell() -> None:
    script = read_script("scripts/run_frontend.ps1")

    assert "frontend" in script
    assert "npm" in script
    assert '$bindAddress = "127.0.0.1"' in script
    assert '[int]$Port = 3000' in script
    assert '$canonicalBrowserUrl = "http://${bindAddress}:$Port"' in script
    assert '@("run", "dev", "--", "--hostname", $bindAddress, "--port", $Port.ToString())' in script


def test_run_frontend_preserves_portable_node_and_prints_launch_diagnostics() -> None:
    script = read_script("scripts/run_frontend.ps1")

    assert "[string]$NodeHome" in script
    assert "Resolve-BlueprintNode -NodeHome $NodeHome" in script
    assert "Configured bind address: $bindAddress" in script
    assert "Configured port: $Port" in script
    assert "Canonical browser URL: $canonicalBrowserUrl" in script
    assert "Node.js version: $($node.NodeVersion)" in script
    assert "npm version: $($node.NpmVersion)" in script
    assert "Node source: $($node.Source)" in script
    assert "Invoke-WebRequest -UseBasicParsing" in script
    assert "Get-NetTCPConnection -State Listen" in script


def test_run_frontend_errors_remain_specific() -> None:
    launcher = read_script("scripts/run_frontend.ps1")
    resolver = read_script("scripts/resolve_node.ps1")

    assert "Node.js and npm were not found on PATH" in resolver
    assert "is too old. BluePrintReboot requires Node.js" in resolver
    assert "Frontend package.json was not found." in launcher
    assert "Frontend dependencies are missing." in launcher
    assert "frontend server process exited with nonzero code" in launcher


def test_run_frontend_is_local_only_and_does_not_permanently_modify_path() -> None:
    launcher = read_script("scripts/run_frontend.ps1")
    resolver = read_script("scripts/resolve_node.ps1")

    assert "0.0.0.0" not in launcher
    assert '"--host"' not in launcher
    assert '"--hostname"' in launcher
    assert "SetEnvironmentVariable" not in launcher
    assert "$previousPath = $env:PATH" in resolver
    assert "$env:PATH = $previousPath" in resolver


def test_dev_setup_uses_venv_and_requirements() -> None:
    script = read_script("scripts/dev_setup.ps1")

    assert ".venv" in script
    assert "requirements.txt" in script
    assert '$ErrorActionPreference = "Stop"' in script
    assert "Python was not found" in script
    assert "requirements.txt was not found" in script


def test_bootstrap_scripts_do_not_contain_obviously_dangerous_commands() -> None:
    script_text = "\n".join(
        read_script(relative_path)
        for relative_path in (
            "scripts/dev_setup.ps1",
            "scripts/frontend_setup.ps1",
            "scripts/dev_check.ps1",
            "scripts/resolve_node.ps1",
            "scripts/run_app.ps1",
            "scripts/run_api.ps1",
            "scripts/run_frontend.ps1",
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
