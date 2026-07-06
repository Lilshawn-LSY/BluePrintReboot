from scripts.smoke_check import PROJECT_ROOT, check_manifest_contract, check_required_paths, main
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
    assert "1.0.13" in result.detail


def test_smoke_check_main_succeeds(capsys) -> None:
    exit_code = main(["--project-root", str(PROJECT_ROOT)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Readiness summary:" in output
    assert "0 failed" in output
