from config.contact import APP_VERSION
from scripts.smoke_check import (
    PROJECT_ROOT,
    check_api_contract,
    check_frontend_contract,
    check_manifest_contract,
    check_repository_hygiene,
    check_required_paths,
    main,
)
from tests.helpers import make_workspace


def test_required_repository_paths_pass() -> None:
    results = check_required_paths(PROJECT_ROOT)

    assert results
    assert all(result.status == "pass" for result in results)


def test_missing_fresh_clone_paths_fail_without_being_created() -> None:
    workspace = make_workspace("smoke-check-missing-paths")
    results = check_required_paths(workspace)

    assert any(result.status == "fail" for result in results)
    assert list(workspace.iterdir()) == []


def test_backup_manifest_contract_passes() -> None:
    result = check_manifest_contract(PROJECT_ROOT)

    assert result.status == "pass"
    assert APP_VERSION in result.detail


def test_repository_hygiene_contract_passes() -> None:
    result = check_repository_hygiene(PROJECT_ROOT)

    assert result.status == "pass"
    assert "tracked entries inspected" in result.detail


def test_api_application_contract_passes_without_starting_server() -> None:
    result = check_api_contract()

    assert result.status == "pass"
    assert APP_VERSION in result.detail


def test_frontend_application_contract_passes_without_starting_server() -> None:
    result = check_frontend_contract(PROJECT_ROOT)

    assert result.status == "pass"
    assert f"v{APP_VERSION}" in result.detail


def test_smoke_check_main_succeeds(capsys) -> None:
    exit_code = main(["--project-root", str(PROJECT_ROOT)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Readiness summary:" in output
    assert "0 failed" in output
