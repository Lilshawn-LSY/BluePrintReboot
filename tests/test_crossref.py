from urllib.error import HTTPError, URLError
from unittest.mock import Mock

import pytest

from ingest.crossref import (
    CrossrefLookupError,
    check_crossref_connectivity,
    crossref_work_url,
    fetch_crossref_by_doi,
    parse_crossref_work,
    proxy_environment,
)


def test_parse_crossref_work_prefers_print_year_and_formats_authors() -> None:
    parsed = parse_crossref_work(
        {
            "title": ["A Crossref Paper"],
            "author": [
                {"family": "Curie", "given": "Marie"},
                {"family": "Einstein", "given": "Albert"},
            ],
            "published-print": {"date-parts": [[1998, 1, 1]]},
            "published-online": {"date-parts": [[1997, 1, 1]]},
            "issued": {"date-parts": [[1996, 1, 1]]},
            "container-title": ["Journal of Local Research"],
            "DOI": "10.1234/ABC",
        }
    )

    assert parsed["title"] == "A Crossref Paper"
    assert parsed["authors"] == "Curie Marie; Einstein Albert"
    assert parsed["year"] == "1998"
    assert parsed["journal"] == "Journal of Local Research"
    assert parsed["doi"] == "10.1234/abc"
    assert parsed["metadata_source"] == "crossref"
    assert parsed["metadata_confidence"] == "high"
    assert parsed["metadata_checked_at"]


def test_parse_crossref_work_year_fallback_and_missing_author_fields() -> None:
    parsed = parse_crossref_work(
        {
            "title": ["Fallback Paper"],
            "author": [
                {"family": "Onlyfamily"},
                {"given": "Onlygiven"},
                {},
            ],
            "issued": {"date-parts": [["2020"]]},
            "container-title": [],
        }
    )

    assert parsed["authors"] == "Onlyfamily; Onlygiven"
    assert parsed["year"] == "2020"
    assert parsed["journal"] == ""
    assert parsed["doi"] == ""


def test_crossref_work_url_encodes_doi() -> None:
    assert crossref_work_url("10.1145/3368089.3409742") == (
        "https://api.crossref.org/works/10.1145%2F3368089.3409742"
    )


def test_fetch_crossref_by_doi_connection_refused_is_user_friendly(monkeypatch) -> None:
    def fail_urlopen(*args, **kwargs):
        raise URLError(ConnectionRefusedError(10061, "connection refused"))

    monkeypatch.setattr("ingest.crossref.urlopen", fail_urlopen)

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1145/3368089.3409742")

    message = str(exc_info.value)
    assert "Connection to Crossref was refused" in message
    assert "firewall" in message


def test_fetch_crossref_by_doi_429_is_user_friendly(monkeypatch) -> None:
    def fail_urlopen(*args, **kwargs):
        raise HTTPError("https://api.crossref.org/works/x", 429, "Too Many Requests", {}, None)

    monkeypatch.setattr("ingest.crossref.urlopen", fail_urlopen)

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1145/3368089.3409742")

    assert "rate limited" in str(exc_info.value)


def test_check_crossref_connectivity_handles_dns_failure(monkeypatch) -> None:
    def fail_urlopen(*args, **kwargs):
        raise URLError("getaddrinfo failed")

    monkeypatch.setattr("ingest.crossref.urlopen", fail_urlopen)

    result = check_crossref_connectivity()

    assert result["ok"] is False
    assert result["status_code"] == ""
    assert result["error_type"] == "dns"
    assert "api.crossref.org" in result["message"]


def test_check_crossref_connectivity_success(monkeypatch) -> None:
    response = Mock()
    response.status = 200
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    monkeypatch.setattr("ingest.crossref.urlopen", Mock(return_value=response))

    result = check_crossref_connectivity()

    assert result["ok"] is True
    assert result["status_code"] == 200
    assert result["error_type"] == ""


def test_proxy_environment_sanitizes_credentials(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@proxy.example:8080")
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("ALL_PROXY", raising=False)

    assert proxy_environment() == {
        "HTTPS_PROXY": "http://<credentials-hidden>@proxy.example:8080",
    }
