from pathlib import Path

from config.contact import APP_VERSION, DEFAULT_CONTACT_EMAIL, build_blueprint_user_agent, get_contact_email


def test_app_version_is_v1_1_2() -> None:
    assert APP_VERSION == "1.1.2"


def test_contact_email_prefers_crossref_mailto(monkeypatch) -> None:
    monkeypatch.setenv("CROSSREF_MAILTO", "crossref@example.edu")
    monkeypatch.setenv("BLUEPRINT_CONTACT_EMAIL", "blueprint@example.edu")

    assert get_contact_email() == "crossref@example.edu"


def test_contact_email_uses_blueprint_contact_email(monkeypatch) -> None:
    monkeypatch.delenv("CROSSREF_MAILTO", raising=False)
    monkeypatch.setenv("BLUEPRINT_CONTACT_EMAIL", "blueprint@example.edu")

    assert get_contact_email() == "blueprint@example.edu"


def test_contact_email_uses_central_default(monkeypatch) -> None:
    monkeypatch.delenv("CROSSREF_MAILTO", raising=False)
    monkeypatch.delenv("BLUEPRINT_CONTACT_EMAIL", raising=False)

    assert get_contact_email() == DEFAULT_CONTACT_EMAIL


def test_user_agent_uses_resolved_contact_email(monkeypatch) -> None:
    monkeypatch.setenv("CROSSREF_MAILTO", "polite@example.edu")

    assert build_blueprint_user_agent() == f"BluePrintReboot/{APP_VERSION} (mailto:polite@example.edu)"


def test_default_email_literal_is_centralized() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source_roots = ("config", "core", "ingest", "services", "storage", "ui_streamlit", "tests")
    occurrences: list[str] = []
    for root_name in source_roots:
        for path in (project_root / root_name).rglob("*.py"):
            if "_tmp" in path.parts:
                continue
            if DEFAULT_CONTACT_EMAIL in path.read_text(encoding="utf-8"):
                occurrences.append(path.relative_to(project_root).as_posix())

    assert occurrences == ["config/contact.py"]
