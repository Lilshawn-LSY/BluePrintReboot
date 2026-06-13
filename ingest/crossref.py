from __future__ import annotations

import json
import os
import socket
import ssl
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ingest.doi import is_probable_doi, normalize_doi


class CrossrefLookupError(Exception):
    pass


CROSSREF_BASE_URL = "https://api.crossref.org"
USER_AGENT = "BluePrintReboot/0.3.1 (mailto:local@example.invalid)"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def crossref_work_url(doi: str) -> str:
    return f"{CROSSREF_BASE_URL}/works/{quote(normalize_doi(doi), safe='')}"


def fetch_crossref_by_doi(doi: str, timeout: float = 8.0) -> dict[str, Any]:
    normalized = normalize_doi(doi)
    if not normalized:
        raise CrossrefLookupError("Enter a DOI before looking up Crossref metadata.")
    if not is_probable_doi(normalized):
        raise CrossrefLookupError("The DOI does not look valid.")

    request = Request(crossref_work_url(normalized), headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            if status_code == 429:
                raise CrossrefLookupError("Crossref rate limited this lookup. Try again later.")
            if status_code >= 400:
                raise CrossrefLookupError(f"Crossref returned HTTP {status_code}.")
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise CrossrefLookupError("Crossref did not find metadata for this DOI.") from exc
        if exc.code == 429:
            raise CrossrefLookupError("Crossref rate limited this lookup. Try again later.") from exc
        raise CrossrefLookupError(f"Crossref returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise CrossrefLookupError(_network_error_message(exc.reason)) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise CrossrefLookupError("Crossref lookup timed out.") from exc
    except ssl.SSLError as exc:
        raise CrossrefLookupError(f"Could not securely connect to Crossref: {exc}") from exc
    except OSError as exc:
        raise CrossrefLookupError(_network_error_message(exc)) from exc
    except json.JSONDecodeError as exc:
        raise CrossrefLookupError("Crossref returned invalid JSON.") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
        raise CrossrefLookupError("Crossref response did not include work metadata.")
    return payload["message"]


def check_crossref_connectivity(timeout: float = 5.0) -> dict[str, Any]:
    request = Request(f"{CROSSREF_BASE_URL}/works?rows=0", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 400:
                return {
                    "ok": True,
                    "status_code": status_code,
                    "error_type": "",
                    "message": "Crossref is reachable.",
                }
            return {
                "ok": False,
                "status_code": status_code,
                "error_type": "http",
                "message": f"Crossref returned HTTP {status_code}.",
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "status_code": exc.code,
            "error_type": "http",
            "message": _http_error_message(exc.code),
        }
    except URLError as exc:
        return {
            "ok": False,
            "status_code": "",
            "error_type": _network_error_type(exc.reason),
            "message": _network_error_message(exc.reason),
        }
    except (TimeoutError, socket.timeout) as exc:
        return {
            "ok": False,
            "status_code": "",
            "error_type": "timeout",
            "message": "Crossref connection timed out.",
        }
    except ssl.SSLError as exc:
        return {
            "ok": False,
            "status_code": "",
            "error_type": "ssl",
            "message": f"Could not securely connect to Crossref: {exc}",
        }
    except OSError as exc:
        return {
            "ok": False,
            "status_code": "",
            "error_type": _network_error_type(exc),
            "message": _network_error_message(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": "",
            "error_type": "unexpected",
            "message": f"Unexpected Crossref connectivity error: {exc}",
        }


def proxy_environment() -> dict[str, str]:
    proxy_vars = {}
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        value = os.environ.get(name)
        if value:
            proxy_vars[name] = _sanitize_proxy_value(value)
    return proxy_vars


def parse_crossref_work(message: dict[str, Any]) -> dict[str, str]:
    return {
        "title": _first_string(message.get("title")),
        "authors": _format_authors(message.get("author")),
        "year": _publication_year(message),
        "journal": _first_string(message.get("container-title")),
        "doi": normalize_doi(str(message.get("DOI", ""))),
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


def _http_error_message(status_code: int) -> str:
    if status_code == 404:
        return "Crossref did not find metadata for this DOI."
    if status_code == 429:
        return "Crossref rate limited this request. Try again later."
    return f"Crossref returned HTTP {status_code}."


def _network_error_type(error: Any) -> str:
    text = str(error).lower()
    if isinstance(error, TimeoutError) or "timed out" in text:
        return "timeout"
    if isinstance(error, socket.gaierror) or "getaddrinfo" in text or "name resolution" in text:
        return "dns"
    if isinstance(error, ConnectionRefusedError) or "10061" in text or "connection refused" in text:
        return "connection_refused"
    if isinstance(error, ssl.SSLError) or "ssl" in text or "certificate" in text:
        return "ssl"
    return "network"


def _network_error_message(error: Any) -> str:
    error_type = _network_error_type(error)
    if error_type == "timeout":
        return "Crossref connection timed out. Check your network or try again later."
    if error_type == "dns":
        return "Could not resolve api.crossref.org. Check DNS, VPN, proxy, or offline status."
    if error_type == "connection_refused":
        return "Connection to Crossref was refused. This often means a restricted network, firewall, proxy, or offline environment."
    if error_type == "ssl":
        return "Could not securely connect to Crossref. Check SSL inspection, proxy, or certificate settings."
    return f"Could not reach Crossref. Check your network, firewall, proxy, or offline status. Details: {error}"


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
            formatted.append(f"{family} {given}")
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
