from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api import dependencies
from api.adapters import PaperContractError, adapt_paper_detail, adapt_paper_list_item
from api.main import UNAVAILABLE_DETAIL, create_app
from api.schemas import PaperDetail, PaperListItem


def paper_item(
    paper_id: str,
    title: str,
    *,
    archived: object = False,
    year: object = "2025",
    tags: object = None,
) -> dict[str, object]:
    return {
        "paper_id": paper_id,
        "title": title,
        "first_author": "Example Author",
        "year": year,
        "status": "reading",
        "priority": "normal",
        "tags": ["methods"] if tags is None else tags,
        "archived": archived,
        "missing_pdf": False,
        "health": [],
    }


def paper_detail(paper_id: str, title: str, *, archived: object = False) -> dict[str, object]:
    return {
        **paper_item(paper_id, title, archived=archived),
        "authors": ["Example Author", "Second, Author"],
        "journal": "Journal of API Contracts",
        "abstract": "Complete abstract.\n\nA second paragraph is preserved.",
        "keywords": ["paper APIs", "metadata"],
        "arxiv_id": "2501.12345",
        "filename": f"{paper_id}.pdf",
        "relative_pdf_path": f"papers/{paper_id}.pdf",
        "doi": "10.1000/example",
        "project_links": [{"project_id": "project-1", "link_type": "supports", "target_type": "paper"}],
        "note_available": True,
        "extracted_text_available": False,
        "profile_available": True,
        "lifecycle_state": "archived" if archived else "active",
        "recoverable_warnings": [],
        "filepath": "C:/private/library/paper.pdf",
        "pdf_sha256": "private-storage-value",
        "metadata_source": "internal",
    }


@pytest.fixture
def papers() -> list[dict[str, object]]:
    return [
        paper_item("z-active", "Zulu Paper"),
        paper_item("archived", "Archived Paper", archived=True),
        paper_item("a-active", "Alpha Paper"),
        paper_item("same-b", "Same Paper"),
        paper_item("same-a", "Same Paper"),
    ]


def client_for(
    papers: list[dict[str, object]],
    details: dict[str, dict[str, object]] | None = None,
) -> TestClient:
    application = create_app()
    application.dependency_overrides[dependencies.get_paper_list_items] = lambda: deepcopy(papers)

    def detail_provider(paper_id: str):
        return deepcopy((details or {}).get(paper_id))

    application.dependency_overrides[dependencies.get_paper_detail] = detail_provider
    return TestClient(application)


def test_default_collection_returns_active_papers_with_default_pagination(papers) -> None:
    response = client_for(papers).get("/papers")

    assert response.status_code == 200
    body = response.json()
    assert [item["paper_id"] for item in body["items"]] == ["a-active", "same-a", "same-b", "z-active"]
    assert body == {
        "items": body["items"],
        "total": 4,
        "limit": 20,
        "offset": 0,
        "has_more": False,
    }
    assert all(item["archived"] is False for item in body["items"])


@pytest.mark.parametrize(
    "archive_status,expected",
    [
        ("active", ["a-active", "same-a", "same-b", "z-active"]),
        ("archived", ["archived"]),
        ("all", ["a-active", "archived", "same-a", "same-b", "z-active"]),
    ],
)
def test_archive_filters(papers, archive_status: str, expected: list[str]) -> None:
    response = client_for(papers).get("/papers", params={"archive_status": archive_status})

    assert response.status_code == 200
    assert [item["paper_id"] for item in response.json()["items"]] == expected
    assert response.json()["total"] == len(expected)


def test_empty_collection_returns_empty_envelope() -> None:
    response = client_for([]).get("/papers")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0, "has_more": False}


def test_normal_and_offset_pagination_preserve_filtered_total_and_has_more(papers) -> None:
    first = client_for(papers).get("/papers", params={"limit": 2})
    second = client_for(papers).get("/papers", params={"limit": 2, "offset": 2})

    assert [item["paper_id"] for item in first.json()["items"]] == ["a-active", "same-a"]
    assert first.json() | {"items": []} == {"items": [], "total": 4, "limit": 2, "offset": 0, "has_more": True}
    assert [item["paper_id"] for item in second.json()["items"]] == ["same-b", "z-active"]
    assert second.json() | {"items": []} == {"items": [], "total": 4, "limit": 2, "offset": 2, "has_more": False}


def test_offset_beyond_total_is_successful_and_empty(papers) -> None:
    response = client_for(papers).get("/papers", params={"offset": 99})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 4, "limit": 20, "offset": 99, "has_more": False}


def test_ordering_is_deterministic_for_unsorted_input_and_title_ties(papers) -> None:
    forward = client_for(papers).get("/papers", params={"archive_status": "all"}).json()["items"]
    reverse = client_for(list(reversed(papers))).get("/papers", params={"archive_status": "all"}).json()["items"]

    assert [item["paper_id"] for item in forward] == [item["paper_id"] for item in reverse]
    assert [item["paper_id"] for item in forward] == ["a-active", "archived", "same-a", "same-b", "z-active"]


@pytest.mark.parametrize("limit", [1, 100])
def test_minimum_and_maximum_limits_are_valid(papers, limit: int) -> None:
    response = client_for(papers).get("/papers", params={"limit": limit})

    assert response.status_code == 200
    assert response.json()["limit"] == limit


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": -1},
        {"limit": 101},
        {"offset": -1},
        {"archive_status": "deleted"},
    ],
)
def test_invalid_collection_parameters_return_validation_errors(papers, params) -> None:
    response = client_for(papers).get("/papers", params=params)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_active_and_archived_paper_details_are_directly_retrievable() -> None:
    details = {
        "active": paper_detail("active", "Active Paper"),
        "archived": paper_detail("archived", "Archived Paper", archived=True),
    }
    client = client_for([], details)

    active = client.get("/papers/active")
    archived = client.get("/papers/archived")

    assert active.status_code == archived.status_code == 200
    assert active.json()["lifecycle_state"] == "active"
    assert active.json()["authors"] == ["Example Author", "Second, Author"]
    assert active.json()["journal"] == "Journal of API Contracts"
    assert active.json()["abstract"] == "Complete abstract.\n\nA second paragraph is preserved."
    assert active.json()["keywords"] == ["paper APIs", "metadata"]
    assert active.json()["arxiv_id"] == "2501.12345"
    assert archived.json()["archived"] is True
    assert archived.json()["lifecycle_state"] == "archived"


def test_unknown_paper_returns_consistent_404() -> None:
    response = client_for([]).get("/papers/unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": "Paper not found."}


def test_detail_matches_schema_without_internal_storage_fields() -> None:
    response = client_for([], {"paper": paper_detail("paper", "Public Paper")}).get("/papers/paper")

    assert response.status_code == 200
    parsed = PaperDetail.model_validate(response.json())
    assert parsed.paper_id == "paper"
    assert not {"filepath", "pdf_sha256", "metadata_source"} & set(response.json())
    assert not parsed.relative_pdf_path.startswith(("/", "C:"))


def test_missing_rich_metadata_and_missing_pdf_remain_successful() -> None:
    source = paper_detail("missing", "Missing Metadata")
    for field in ("authors", "journal", "abstract", "keywords", "arxiv_id"):
        source.pop(field)
    source["missing_pdf"] = True
    source["relative_pdf_path"] = ""

    response = client_for([], {"missing": source}).get("/papers/missing")

    assert response.status_code == 200
    body = response.json()
    assert body["authors"] == [] and body["keywords"] == []
    assert body["journal"] == body["abstract"] == body["arxiv_id"] == ""
    assert body["missing_pdf"] is True and body["relative_pdf_path"] == ""


def test_storage_failure_is_not_converted_to_false_404(monkeypatch) -> None:
    def fail(_paper_id: str):
        raise OSError("private storage failed")

    monkeypatch.setattr(dependencies.library_read_model, "build_paper_detail", fail)
    response = TestClient(create_app()).get("/papers/known")

    assert response.status_code == 503
    assert response.json() == {"detail": UNAVAILABLE_DETAIL}
    assert "private storage failed" not in response.text


def test_adapter_normalizes_complete_domain_item() -> None:
    adapted = adapt_paper_list_item(
        paper_item("paper", " Paper Title ", archived="TRUE", year=2024.0, tags=" one, two ,, ")
    )

    assert isinstance(adapted, PaperListItem)
    assert adapted.title == "Paper Title"
    assert adapted.archived is True
    assert adapted.year == "2024"
    assert adapted.tags == ["one", "two"]


def test_adapter_normalizes_complete_rich_detail_and_preserves_abstract() -> None:
    source = paper_detail("paper", "Paper Title")
    source.update(
        {
            "authors": " Alpha Author ; Beta, Author ",
            "journal": " Journal Name ",
            "abstract": "  First paragraph.\n\nSecond paragraph.  ",
            "keywords": " single-cell RNA, deep learning ",
            "arxiv_id": " 2501.12345 ",
        }
    )

    adapted = adapt_paper_detail(source)

    assert adapted.authors == ["Alpha Author", "Beta, Author"]
    assert adapted.journal == "Journal Name"
    assert adapted.abstract == "First paragraph.\n\nSecond paragraph."
    assert adapted.keywords == ["single-cell RNA", "deep learning"]
    assert adapted.arxiv_id == "2501.12345"


def test_adapter_rich_metadata_defaults_and_nan_are_safe() -> None:
    source = paper_detail("paper", "Paper Title")
    source.update({"authors": None, "journal": float("nan"), "abstract": None, "keywords": float("nan"), "arxiv_id": None})

    adapted = adapt_paper_detail(source)

    assert adapted.authors == [] and adapted.keywords == []
    assert adapted.journal == adapted.abstract == adapted.arxiv_id == ""


def test_adapter_normalizes_missing_optional_metadata_and_archive_default() -> None:
    adapted = adapt_paper_list_item({"paper_id": "paper", "title": "Title"})

    assert adapted.first_author == ""
    assert adapted.year == ""
    assert adapted.status == "unread"
    assert adapted.priority == "normal"
    assert adapted.tags == []
    assert adapted.archived is False
    assert adapted.missing_pdf is False


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), ("yes", True), ("0", False), (1, True)])
def test_adapter_normalizes_boolean_values(value: object, expected: bool) -> None:
    adapted = adapt_paper_list_item(paper_item("paper", "Title", archived=value))

    assert adapted.archived is expected


@pytest.mark.parametrize("field", ["paper_id", "title"])
def test_adapter_rejects_missing_required_identity(field: str) -> None:
    source = paper_item("paper", "Title")
    source[field] = ""

    with pytest.raises(PaperContractError):
        adapt_paper_list_item(source)


def test_adapter_rejects_unsafe_absolute_detail_path() -> None:
    source = paper_detail("paper", "Title")
    source["relative_pdf_path"] = "C:/private/library/paper.pdf"

    with pytest.raises(PaperContractError):
        adapt_paper_detail(source)


def test_collection_items_remain_lightweight_without_rich_metadata(papers) -> None:
    response = client_for(papers).get("/papers", params={"archive_status": "all"})

    assert response.status_code == 200
    rich_fields = {"authors", "journal", "abstract", "keywords", "arxiv_id"}
    assert all(not rich_fields & set(item) for item in response.json()["items"])


def test_openapi_documents_paper_contracts_pagination_enum_and_404() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    list_operation = paths["/papers"]["get"]
    detail_operation = paths["/papers/{paper_id}"]["get"]

    assert "/papers" in paths
    assert "/papers/{paper_id}" in paths
    assert list_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PaginatedPaperList")
    assert detail_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PaperDetail")
    assert detail_operation["responses"]["404"]["content"]["application/json"]["schema"]["$ref"].endswith("/APIError")
    parameters = {parameter["name"]: parameter for parameter in list_operation["parameters"]}
    assert {"limit", "offset", "archive_status"} <= set(parameters)
    archive_schema = parameters["archive_status"]["schema"]
    enum_ref = archive_schema.get("$ref") or archive_schema["allOf"][0]["$ref"]
    enum_name = enum_ref.rsplit("/", 1)[-1]
    assert schema["components"]["schemas"][enum_name]["enum"] == ["active", "archived", "all"]
    detail_schema = schema["components"]["schemas"]["PaperDetail"]
    list_schema = schema["components"]["schemas"]["PaperListItem"]
    rich_fields = {"authors", "journal", "abstract", "keywords", "arxiv_id"}
    assert rich_fields <= set(detail_schema["properties"])
    assert not rich_fields & set(list_schema["properties"])
    assert detail_schema["properties"]["authors"]["items"]["type"] == "string"
    assert detail_schema["properties"]["authors"]["type"] == "array"
    assert detail_schema["properties"]["keywords"]["type"] == "array"
    assert all(detail_schema["properties"][field]["type"] == "string" for field in ("journal", "abstract", "arxiv_id"))
    assert rich_fields <= set(detail_schema["example"])
