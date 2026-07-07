from unittest.mock import Mock

import pytest
import requests

from ingest.crossref import (
    CrossrefLookupError,
    check_crossref_connectivity,
    crossref_connectivity_url,
    crossref_headers,
    crossref_work_url,
    fetch_crossref_by_doi,
    lookup_crossref_metadata,
    parse_crossref_work,
    proxy_environment,
)


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: object = None, json_error: Exception | None = None) -> None:
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


def complete_work() -> dict:
    return {
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
        "abstract": "<jats:p>Structured <jats:bold>abstract</jats:bold> text.</jats:p>",
        "subject": ["Synthetic Biology", "Methods"],
    }


def test_parse_crossref_work_extracts_supported_metadata() -> None:
    parsed = parse_crossref_work(complete_work())

    assert parsed["title"] == "A Crossref Paper"
    assert parsed["authors"] == "Marie Curie; Albert Einstein"
    assert parsed["year"] == "1998"
    assert parsed["journal"] == "Journal of Local Research"
    assert parsed["doi"] == "10.1234/abc"
    assert parsed["abstract"] == "Structured abstract text."
    assert parsed["keywords"] == "Synthetic Biology, Methods"
    assert parsed["crossref_subjects"] == "Synthetic Biology, Methods"
    assert parsed["metadata_source"] == "crossref"
    assert parsed["metadata_confidence"] == "high"
    assert parsed["metadata_checked_at"]


def test_parse_crossref_work_year_fallback_and_missing_author_fields() -> None:
    parsed = parse_crossref_work(
        {
            "title": ["Fallback Paper"],
            "author": [{"family": "Onlyfamily"}, {"given": "Onlygiven"}, {}],
            "issued": {"date-parts": [["2020"]]},
            "container-title": [],
        }
    )

    assert parsed["authors"] == "Onlyfamily; Onlygiven"
    assert parsed["year"] == "2020"
    assert parsed["journal"] == ""
    assert parsed["doi"] == ""


def test_crossref_work_url_encodes_doi_and_includes_mailto(monkeypatch) -> None:
    monkeypatch.setenv("CROSSREF_MAILTO", "researcher@example.edu")

    assert crossref_work_url("doi: 10.1145/3368089.3409742") == (
        "https://api.crossref.org/works/10.1145%2F3368089.3409742?mailto=researcher@example.edu"
    )


def test_crossref_headers_use_blueprint_user_agent(monkeypatch) -> None:
    monkeypatch.setenv("CROSSREF_MAILTO", "researcher@example.edu")

    headers = crossref_headers()

    assert headers["User-Agent"] == "BluePrintReboot/1.0.17 (mailto:researcher@example.edu)"
    assert headers["Accept"] == "application/json"


def test_fetch_crossref_uses_polite_url_headers_and_timeout(monkeypatch) -> None:
    monkeypatch.setenv("CROSSREF_MAILTO", "researcher@example.edu")
    request = Mock(return_value=FakeResponse(payload={"message": complete_work()}))
    monkeypatch.setattr("ingest.crossref.requests.get", request)

    message = fetch_crossref_by_doi("10.1234/ABC", timeout=3.5)

    assert message["title"] == ["A Crossref Paper"]
    request.assert_called_once_with(
        "https://api.crossref.org/works/10.1234%2Fabc?mailto=researcher@example.edu",
        headers={
            "Accept": "application/json",
            "User-Agent": "BluePrintReboot/1.0.17 (mailto:researcher@example.edu)",
        },
        timeout=3.5,
    )


def test_lookup_crossref_metadata_reports_partial_fields(monkeypatch) -> None:
    work = complete_work()
    work["author"] = []
    monkeypatch.setattr(
        "ingest.crossref.requests.get",
        Mock(return_value=FakeResponse(payload={"message": work})),
    )

    metadata = lookup_crossref_metadata("10.1234/abc")

    assert metadata["title"] == "A Crossref Paper"
    assert metadata["authors"] == ""
    assert metadata["metadata_confidence"] == "partial"
    assert "Fill missing fields manually" in metadata["metadata_warning"]


def test_lookup_crossref_metadata_rejects_missing_core_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.crossref.requests.get",
        Mock(return_value=FakeResponse(payload={"message": {"DOI": "10.1234/abc"}})),
    )

    with pytest.raises(CrossrefLookupError) as exc_info:
        lookup_crossref_metadata("10.1234/abc")

    assert exc_info.value.error_type == "missing_metadata"
    assert str(exc_info.value) == (
        "Crossref lookup succeeded, but title/year/author metadata was incomplete. "
        "Fill missing fields manually before using Paper File Hygiene."
    )


def test_fetch_crossref_timeout_is_classified(monkeypatch) -> None:
    monkeypatch.setattr("ingest.crossref.requests.get", Mock(side_effect=requests.exceptions.Timeout()))

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1234/abc")

    assert exc_info.value.error_type == "timeout"
    assert str(exc_info.value) == "Crossref lookup timed out. Try again later."


def test_fetch_crossref_network_error_is_classified(monkeypatch) -> None:
    monkeypatch.setattr("ingest.crossref.requests.get", Mock(side_effect=requests.exceptions.ConnectionError()))

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1234/abc")

    assert exc_info.value.error_type == "network"
    assert "network connection failed" in str(exc_info.value)


def test_fetch_crossref_ssl_error_is_classified(monkeypatch) -> None:
    monkeypatch.setattr("ingest.crossref.requests.get", Mock(side_effect=requests.exceptions.SSLError()))

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1234/abc")

    assert exc_info.value.error_type == "ssl"
    assert str(exc_info.value) == (
        "Crossref SSL/certificate check failed. Update certifi or check network inspection."
    )


def test_fetch_crossref_404_is_classified(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.crossref.requests.get",
        Mock(return_value=FakeResponse(status_code=404)),
    )

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1234/abc")

    assert exc_info.value.error_type == "not_found"
    assert exc_info.value.status_code == 404
    assert str(exc_info.value) == "DOI was not found in Crossref."


def test_fetch_crossref_non_200_is_classified(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.crossref.requests.get",
        Mock(return_value=FakeResponse(status_code=503)),
    )

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1234/abc")

    assert exc_info.value.error_type == "http"
    assert exc_info.value.status_code == 503
    assert str(exc_info.value) == "Crossref returned HTTP 503."


def test_fetch_crossref_malformed_json_is_classified(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.crossref.requests.get",
        Mock(return_value=FakeResponse(json_error=ValueError("bad json"))),
    )

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1234/abc")

    assert exc_info.value.error_type == "malformed_json"
    assert str(exc_info.value) == "Crossref returned an unexpected response."


def test_fetch_crossref_missing_message_is_classified(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.crossref.requests.get",
        Mock(return_value=FakeResponse(payload={"status": "ok"})),
    )

    with pytest.raises(CrossrefLookupError) as exc_info:
        fetch_crossref_by_doi("10.1234/abc")

    assert exc_info.value.error_type == "malformed_response"


def test_connectivity_uses_shared_request_helper(monkeypatch) -> None:
    shared_request = Mock(return_value={"status": "ok", "message": {}})
    monkeypatch.setattr("ingest.crossref._request_crossref_json", shared_request)

    result = check_crossref_connectivity(timeout=4.0)

    assert result == {
        "ok": True,
        "status_code": 200,
        "error_type": "",
        "message": "Crossref is reachable.",
    }
    shared_request.assert_called_once_with(crossref_connectivity_url(), 4.0)


def test_connectivity_returns_shared_error_classification(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.crossref._request_crossref_json",
        Mock(
            side_effect=CrossrefLookupError(
                "Crossref lookup timed out. Try again later.",
                error_type="timeout",
            )
        ),
    )

    result = check_crossref_connectivity()

    assert result["ok"] is False
    assert result["error_type"] == "timeout"
    assert result["message"] == "Crossref lookup timed out. Try again later."


def test_proxy_environment_sanitizes_credentials(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@proxy.example:8080")
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("ALL_PROXY", raising=False)

    assert proxy_environment() == {
        "HTTPS_PROXY": "http://<credentials-hidden>@proxy.example:8080",
    }
