from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import dependencies
from api.main import UNAVAILABLE_DETAIL, create_app
from api.schemas import HealthSummaryResponse, LibraryStatusResponse
from config.contact import APP_VERSION, DEFAULT_CONTACT_EMAIL


HEALTH_KEYS = {
    "overall_state",
    "blocking_issues",
    "warning_count",
    "corrupt_critical_state_count",
    "quarantine_count",
    "missing_pdf_count",
    "duplicate_review_count",
}
STATUS_KEYS = {
    "active_count",
    "archived_count",
    "missing_count",
    "duplicate_count",
    "corrupt_count",
    "quarantine_count",
    "degraded",
    "workspace_warnings",
}


def health_payload(state: str = "healthy") -> dict[str, object]:
    return {
        "overall_state": state,
        "blocking_issues": 1 if state == "blocked" else 0,
        "warning_count": 1 if state == "degraded" else 0,
        "corrupt_critical_state_count": 0,
        "quarantine_count": 0,
        "missing_pdf_count": 1 if state == "blocked" else 0,
        "duplicate_review_count": 0,
    }


def status_payload(degraded: bool = False) -> dict[str, object]:
    return {
        "active_count": 3,
        "archived_count": 1,
        "missing_count": 1 if degraded else 0,
        "duplicate_count": 0,
        "corrupt_count": 0,
        "quarantine_count": 0,
        "degraded": degraded,
        "workspace_warnings": ["Some indexed PDFs are missing."] if degraded else [],
    }


@pytest.fixture
def client() -> TestClient:
    application = create_app()
    application.dependency_overrides[dependencies.get_health_summary] = health_payload
    application.dependency_overrides[dependencies.get_library_status] = status_payload
    return TestClient(application)


def test_create_app_returns_fastapi_with_runtime_version() -> None:
    application = create_app()

    assert isinstance(application, FastAPI)
    assert application.version == APP_VERSION


def test_health_returns_exact_contract_and_types(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == HEALTH_KEYS
    assert isinstance(body["overall_state"], str)
    assert all(isinstance(body[key], int) and not isinstance(body[key], bool) for key in HEALTH_KEYS - {"overall_state"})


def test_library_status_returns_exact_contract_and_types(client: TestClient) -> None:
    response = client.get("/library/status")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == STATUS_KEYS
    assert all(isinstance(body[key], int) and not isinstance(body[key], bool) for key in STATUS_KEYS - {"degraded", "workspace_warnings"})
    assert isinstance(body["degraded"], bool)
    assert isinstance(body["workspace_warnings"], list)
    assert all(isinstance(item, str) for item in body["workspace_warnings"])


@pytest.mark.parametrize("state", ["healthy", "degraded", "blocked"])
def test_domain_health_states_remain_successful(state: str) -> None:
    application = create_app()
    application.dependency_overrides[dependencies.get_health_summary] = lambda: health_payload(state)

    response = TestClient(application).get("/health")

    assert response.status_code == 200
    assert response.json()["overall_state"] == state


def test_degraded_library_status_remains_successful() -> None:
    application = create_app()
    application.dependency_overrides[dependencies.get_library_status] = lambda: status_payload(True)

    response = TestClient(application).get("/library/status")

    assert response.status_code == 200
    assert response.json()["degraded"] is True


@pytest.mark.parametrize("endpoint,builder_name", [("/health", "build_health_summary"), ("/library/status", "build_library_status")])
def test_provider_failure_is_generic_and_private(endpoint: str, builder_name: str, monkeypatch, tmp_path: Path) -> None:
    private_path = str(tmp_path / "private" / "paper_index.csv")
    raw_error = "storage exploded while reading private state"
    environment_value = "do-not-expose-this-value"
    monkeypatch.setenv("BLUEPRINT_PRIVATE_TEST_VALUE", environment_value)

    def fail() -> None:
        raise OSError(f"{raw_error}: {private_path}")

    monkeypatch.setattr(dependencies.library_read_model, builder_name, fail)
    response = TestClient(create_app()).get(endpoint)

    assert response.status_code == 503
    assert response.json() == {"detail": UNAVAILABLE_DETAIL}
    serialized = response.text
    for private_value in (private_path, raw_error, environment_value, DEFAULT_CONTACT_EMAIL):
        assert private_value not in serialized


def test_openapi_has_only_intended_application_paths_and_read_methods() -> None:
    application = create_app()
    paths = application.openapi()["paths"]

    assert set(paths) == {"/health", "/library/status"}
    assert all(set(operations) == {"get"} for operations in paths.values())
    unsafe_methods = {"POST", "PUT", "PATCH", "DELETE"}
    assert not any(
        unsafe_methods & (getattr(route, "methods", None) or set())
        for route in application.routes
    )


def test_providers_delegate_to_existing_read_model_builders(monkeypatch) -> None:
    expected_health = health_payload()
    expected_status = status_payload()
    calls: list[str] = []
    monkeypatch.setattr(dependencies.library_read_model, "build_health_summary", lambda: calls.append("health") or expected_health)
    monkeypatch.setattr(dependencies.library_read_model, "build_library_status", lambda: calls.append("status") or expected_status)

    assert dependencies.get_health_summary() == expected_health
    assert dependencies.get_library_status() == expected_status
    assert calls == ["health", "status"]


@pytest.mark.parametrize(
    "model,payload",
    [(HealthSummaryResponse, health_payload()), (LibraryStatusResponse, status_payload())],
)
def test_response_models_forbid_extra_fields(model, payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({**payload, "private_path": "C:/private/library"})


def test_endpoint_calls_do_not_modify_workspace_files(client: TestClient, tmp_path: Path) -> None:
    workspace_file = tmp_path / "paper_index.csv"
    workspace_file.write_bytes(b"paper_id,title\n1,Untouched\n")
    before = (workspace_file.read_bytes(), workspace_file.stat().st_mtime_ns)

    assert client.get("/health").status_code == 200
    assert client.get("/library/status").status_code == 200

    assert (workspace_file.read_bytes(), workspace_file.stat().st_mtime_ns) == before


def test_importing_api_does_not_launch_server_or_modify_workspace(monkeypatch, tmp_path: Path) -> None:
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    before = (sentinel.read_bytes(), sentinel.stat().st_mtime_ns)
    called = False

    def forbidden_run(*_args, **_kwargs) -> None:
        nonlocal called
        called = True

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", forbidden_run)
    import api.main

    importlib.reload(api.main)

    assert called is False
    assert (sentinel.read_bytes(), sentinel.stat().st_mtime_ns) == before
