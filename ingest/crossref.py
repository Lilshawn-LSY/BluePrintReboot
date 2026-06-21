from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode

import certifi
import requests
import urllib3

from config.contact import build_blueprint_user_agent, get_contact_email
from ingest.doi import is_probable_doi, normalize_doi


CROSSREF_BASE_URL = "https://api.crossref.org"
DEFAULT_CROSSREF_TIMEOUT = 8.0
REQUIRED_METADATA_FIELDS = ("title", "year", "authors")


class CrossrefLookupError(Exception):
    def __init__(
        self,
        message: str,
        *,
        error_type: str = "unexpected",
        status_code: int | str = "",
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


def crossref_mailto() -> str:
    return get_contact_email()


def crossref_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "User-Agent": build_blueprint_user_agent(),
    }


def crossref_dependency_versions() -> dict[str, str]:
    return {
        "requests": requests.__version__,
        "urllib3": urllib3.__version__,
        "certifi": certifi.__version__,
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _crossref_url(path: str, **query: object) -> str:
    parameters = {key: str(value) for key, value in query.items()}
    parameters["mailto"] = get_contact_email()
    return f"{CROSSREF_BASE_URL}/{path.lstrip('/')}?{urlencode(parameters, safe='@')}"


def crossref_work_url(doi: str) -> str:
    normalized = normalize_doi(doi)
    return _crossref_url(f"works/{quote(normalized, safe='')}")


def crossref_connectivity_url() -> str:
    return _crossref_url("works", rows=0)


def _request_crossref_json(url: str, timeout: float) -> dict[str, Any]:
    try:
        response = requests.get(url, headers=crossref_headers(), timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise CrossrefLookupError(
            "Crossref lookup timed out. Try again later.",
            error_type="timeout",
        ) from exc
    except requests.exceptions.SSLError as exc:
        raise CrossrefLookupError(
            "Crossref SSL/certificate check failed. Update certifi or check network inspection.",
            error_type="ssl",
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise CrossrefLookupError(
            "Crossref network connection failed. Check your connection, proxy, or firewall.",
            error_type="network",
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise CrossrefLookupError(
            "Crossref request failed unexpectedly. Try again later.",
            error_type="request",
        ) from exc

    if response.status_code != 200:
        raise CrossrefLookupError(
            _http_error_message(response.status_code),
            error_type="not_found" if response.status_code == 404 else "http",
            status_code=response.status_code,
        )

    try:
        payload = response.json()
    except (requests.exceptions.JSONDecodeError, ValueError) as exc:
        raise CrossrefLookupError(
            "Crossref returned an unexpected response.",
            error_type="malformed_json",
            status_code=response.status_code,
        ) from exc
    if not isinstance(payload, dict):
        raise CrossrefLookupError(
            "Crossref returned an unexpected response.",
            error_type="malformed_response",
            status_code=response.status_code,
        )
    return payload


def fetch_crossref_by_doi(doi: str, timeout: float = DEFAULT_CROSSREF_TIMEOUT) -> dict[str, Any]:
    normalized = normalize_doi(doi)
    if not normalized:
        raise CrossrefLookupError(
            "Enter a DOI before looking up Crossref metadata.",
            error_type="invalid_doi",
        )
    if not is_probable_doi(normalized):
        raise CrossrefLookupError("The DOI does not look valid.", error_type="invalid_doi")

    payload = _request_crossref_json(crossref_work_url(normalized), timeout)
    message = payload.get("message")
    if not isinstance(message, dict):
        raise CrossrefLookupError(
            "Crossref returned an unexpected response.",
            error_type="malformed_response",
        )
    return message


def lookup_crossref_metadata(
    doi: str,
    timeout: float = DEFAULT_CROSSREF_TIMEOUT,
) -> dict[str, str]:
    parsed = parse_crossref_work(fetch_crossref_by_doi(doi, timeout=timeout))
    missing = [field for field in REQUIRED_METADATA_FIELDS if not parsed[field]]
    if len(missing) == len(REQUIRED_METADATA_FIELDS):
        raise CrossrefLookupError(
            "Crossref lookup succeeded, but title/year/author metadata was incomplete. "
            "Fill missing fields manually before using Paper File Hygiene.",
            error_type="missing_metadata",
        )
    if missing:
        labels = ", ".join("author" if field == "authors" else field for field in missing)
        parsed["metadata_warning"] = (
            f"Crossref metadata is missing: {labels}. Fill missing fields manually before using Paper File Hygiene."
        )
        parsed["metadata_confidence"] = "partial"
    else:
        parsed["metadata_warning"] = ""
    return parsed


def check_crossref_connectivity(timeout: float = 5.0) -> dict[str, Any]:
    try:
        _request_crossref_json(crossref_connectivity_url(), timeout)
    except CrossrefLookupError as exc:
        return {
            "ok": False,
            "status_code": exc.status_code,
            "error_type": exc.error_type,
            "message": str(exc),
        }
    return {
        "ok": True,
        "status_code": 200,
        "error_type": "",
        "message": "Crossref is reachable.",
    }


def proxy_environment() -> dict[str, str]:
    proxy_vars = {}
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        value = os.environ.get(name)
        if value:
            proxy_vars[name] = _sanitize_proxy_value(value)
    return proxy_vars


def parse_crossref_work(message: dict[str, Any]) -> dict[str, str]:
    subjects = _format_keywords(message.get("subject") or message.get("keyword"))
    return {
        "title": _first_string(message.get("title")),
        "authors": _format_authors(message.get("author")),
        "year": _publication_year(message),
        "journal": _first_string(message.get("container-title")),
        "doi": normalize_doi(str(message.get("DOI", ""))),
        "abstract": _clean_abstract(message.get("abstract")),
        "keywords": subjects,
        "crossref_subjects": subjects,
        "metadata_source": "crossref",
        "metadata_confidence": "high",
        "metadata_checked_at": utc_now_iso(),
    }


def _first_string(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _clean_abstract(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(re.sub(r"<[^>]+>", " ", value).split())


def _format_keywords(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    keywords = [str(item).strip() for item in value if str(item).strip()]
    return ", ".join(keywords)


def _http_error_message(status_code: int) -> str:
    if status_code == 404:
        return "DOI was not found in Crossref."
    if status_code == 429:
        return "Crossref rate limited this request. Try again later."
    return f"Crossref returned HTTP {status_code}."


def _sanitize_proxy_value(value: str) -> str:
    cleaned = value.strip()
    if "@" not in cleaned:
        return cleaned
    scheme_split = cleaned.split("://", 1)
    prefix = f"{scheme_split[0]}://" if len(scheme_split) == 2 else ""
    rest = scheme_split[1] if len(scheme_split) == 2 else cleaned
    host_part = rest.split("@", 1)[1]
    return f"{prefix}<credentials-hidden>@{host_part}"


def _format_authors(authors: Any) -> str:
    if not isinstance(authors, list):
        return ""

    formatted: list[str] = []
    for author in authors:
        if not isinstance(author, dict):
            continue
        family = str(author.get("family", "")).strip()
        given = str(author.get("given", "")).strip()
        if family and given:
            formatted.append(f"{given} {family}")
        elif family:
            formatted.append(family)
        elif given:
            formatted.append(given)
    return "; ".join(formatted)


def _publication_year(message: dict[str, Any]) -> str:
    for field in ("published-print", "published-online", "issued"):
        year = _year_from_date_parts(message.get(field))
        if year:
            return year
    return ""


def _year_from_date_parts(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    date_parts = value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts:
        return ""
    first = date_parts[0]
    if not isinstance(first, list) or not first:
        return ""
    year = first[0]
    if isinstance(year, int):
        return str(year)
    if isinstance(year, str) and year.strip().isdigit():
        return year.strip()
    return ""
