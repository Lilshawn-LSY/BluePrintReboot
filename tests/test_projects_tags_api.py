from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import dependencies
from api.main import UNAVAILABLE_DETAIL, create_app
from api.schemas import (
    CandidateSummaryResponse,
    PaginatedProjectList,
    PaginatedTagList,
    ProjectDetail,
)
from services import project_read_model, tag_book, tag_read_model


def project_item(project_id: str, name: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "name": name,
        "description": f"Description for {name}",
        "status": "active",
        "priority": "normal",
        "tags": ["research"],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-02T00:00:00+00:00",
        "project_revision": "a" * 64,
        "link_count": 1,
        "linked_paper_count": 1,
        "storage_path": "C:/private/projects.json",
    }


def project_detail(project_id: str) -> dict[str, object]:
    return {
        **project_item(project_id, "Project Detail"),
        "links": [
            {
                "link_id": "link-b",
                "link_type": "background",
                "target_type": "paper",
                "target_state": "orphaned",
                "paper_id": "missing-paper",
                "created_at": "2026-01-02T00:00:00+00:00",
                "paper": None,
                "note_block": None,
                "target_id": "missing-paper",
            },
            {
                "link_id": "link-a",
                "link_type": "key_reference",
                "target_type": "paper",
                "target_state": "available",
                "paper_id": "paper-1",
                "target_id": "paper-1",
                "created_at": "2026-01-01T00:00:00+00:00",
                "paper": {
                    "paper_id": "paper-1",
                    "title": "Allowlisted Paper",
                    "first_author": "Author",
                    "year": "2026",
                    "status": "reading",
                    "priority": "high",
                    "tags": ["methods"],
                    "archived": False,
                    "filepath": "C:/private/paper.pdf",
                },
                "note_block": None,
            },
        ],
        "link_count": 2,
        "linked_paper_count": 2,
        "links_revision": "b" * 64,
        "orphaned_link_count": 1,
    }


def canonical_tag(key: str, label: str) -> dict[str, object]:
    return {
        "canonical_key": key,
        "label": label,
        "category": "field",
        "aliases": [f"{label} alias"],
        "status": "active",
        "suggestion_strength": 7,
        "source_paths": ["C:/private/tag_book.json"],
    }


def candidate_summary(*, available: bool = True) -> dict[str, object]:
    return {
        "availability": "available" if available else "unavailable",
        "state": "populated" if available else "unavailable",
        "source": "paper_index" if available else "none",
        "evaluated_paper_count": 2 if available else 0,
        "candidate_count": 3 if available else 0,
        "known_canonical_match_count": 1 if available else 0,
        "quality_counts": {
            "high": 1 if available else 0,
            "medium": 1 if available else 0,
            "weak": 1 if available else 0,
            "rejected": 0,
        },
    }


def client_for(
    *,
    projects: list[dict[str, object]] | None = None,
    details: dict[str, dict[str, object]] | None = None,
    tags: list[dict[str, object]] | None = None,
    fallback: bool = False,
    summary: dict[str, object] | None = None,
) -> TestClient:
    application = create_app()
    application.dependency_overrides[dependencies.get_project_list_items] = (
        lambda: deepcopy(projects or [])
    )

    def detail_provider(project_id: str):
        return deepcopy((details or {}).get(project_id))

    application.dependency_overrides[dependencies.get_project_detail] = detail_provider
    application.dependency_overrides[dependencies.get_canonical_tags] = (
        lambda: (deepcopy(tags or []), fallback)
    )
    application.dependency_overrides[dependencies.get_candidate_summary] = (
        lambda: deepcopy(summary or candidate_summary())
    )
    return TestClient(application)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_tag_book(base_dir: Path, tags: list[dict[str, object]]) -> None:
    _write_json(base_dir / "tag_book.json", {"version": "2", "tags": tags})


def _write_index(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(path, index=False)


def test_projects_list_is_deterministic_paginated_and_allowlisted() -> None:
    projects = [
        project_item("z", "Zulu"),
        project_item("same-b", "Same"),
        project_item("a", "Alpha"),
        project_item("same-a", "Same"),
    ]
    response = client_for(projects=projects).get(
        "/projects",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert PaginatedProjectList.model_validate(body)
    assert [item["project_id"] for item in body["items"]] == ["same-a", "same-b"]
    assert body | {"items": []} == {
        "items": [],
        "total": 4,
        "limit": 2,
        "offset": 1,
        "has_more": True,
    }
    assert all("storage_path" not in item for item in body["items"])


def test_projects_empty_and_offset_beyond_total_are_valid() -> None:
    empty = client_for().get("/projects")
    beyond = client_for(projects=[project_item("one", "One")]).get(
        "/projects",
        params={"offset": 99},
    )

    assert empty.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
        "has_more": False,
    }
    assert beyond.json()["items"] == []
    assert beyond.json()["total"] == 1
    assert beyond.json()["has_more"] is False


@pytest.mark.parametrize(
    "path,params",
    [
        ("/projects", {"limit": 0}),
        ("/projects", {"limit": 101}),
        ("/projects", {"offset": -1}),
        ("/projects/project", {"links_limit": 0}),
        ("/projects/project", {"links_limit": 101}),
        ("/projects/project", {"links_offset": -1}),
        ("/tags", {"limit": 0}),
        ("/tags", {"limit": 101}),
        ("/tags", {"offset": -1}),
    ],
)
def test_invalid_project_and_tag_pagination_returns_422(path: str, params: dict[str, int]) -> None:
    response = client_for(details={"project": project_detail("project")}).get(
        path,
        params=params,
    )

    assert response.status_code == 422


def test_project_detail_paginates_links_and_preserves_orphan_state() -> None:
    response = client_for(
        details={"project": project_detail("project")},
    ).get("/projects/project", params={"links_limit": 1, "links_offset": 1})

    assert response.status_code == 200
    body = response.json()
    assert ProjectDetail.model_validate_json(response.text)
    assert body["links_total"] == 2
    assert body["links_has_more"] is False
    assert body["orphaned_link_count"] == 1
    assert body["links"][0]["target_state"] == "orphaned"
    assert body["links"][0]["paper"] is None
    assert body["links"][0]["target_id"] == "missing-paper"


def test_project_detail_exposes_only_allowlisted_linked_paper_summary() -> None:
    response = client_for(
        details={"project": project_detail("project")},
    ).get("/projects/project", params={"links_limit": 1})

    paper = response.json()["links"][0]["paper"]
    assert paper["title"] == "Allowlisted Paper"
    assert paper["tags"] == ["methods"]
    assert "filepath" not in paper
    assert "C:/private" not in response.text


def test_unknown_project_returns_404() -> None:
    response = client_for().get("/projects/unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found."}


def test_tags_are_deterministic_paginated_and_allowlisted() -> None:
    tags = [
        canonical_tag("zulu", "Zulu"),
        canonical_tag("same-b", "Same"),
        canonical_tag("alpha", "Alpha"),
        canonical_tag("same-a", "Same"),
    ]
    response = client_for(tags=tags, fallback=True).get(
        "/tags",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert PaginatedTagList.model_validate(body)
    assert [item["canonical_key"] for item in body["items"]] == ["same-a", "same-b"]
    assert body["source_state"] == "legacy_fallback"
    assert body["has_more"] is True
    assert "source_paths" not in response.text
    assert "C:/private" not in response.text


def test_empty_tag_book_and_candidate_summary_states_are_explicit() -> None:
    tags = client_for(summary=candidate_summary(available=False)).get("/tags")
    summary_response = client_for(
        summary=candidate_summary(available=False),
    ).get("/tags/summary")

    assert tags.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
        "has_more": False,
        "source_state": "canonical",
    }
    assert CandidateSummaryResponse.model_validate(summary_response.json())
    assert summary_response.json()["availability"] == "unavailable"
    assert summary_response.json()["state"] == "unavailable"
    assert summary_response.json()["candidate_count"] == 0


def test_candidate_summary_returns_only_fixed_real_counts() -> None:
    response = client_for(summary=candidate_summary()).get("/tags/summary")

    assert response.status_code == 200
    assert response.json() == candidate_summary()
    assert not {"candidates", "source_paths", "records"} & set(response.json())


def test_project_read_model_uses_real_links_and_orphans_without_path_leaks(tmp_path: Path) -> None:
    projects_dir = tmp_path / "projects"
    index_csv = tmp_path / "paper_index.csv"
    _write_json(
        projects_dir / "projects.json",
        [
            {
                "id": "project-1",
                "name": "Real Project",
                "description": "Stored description",
                "status": "active",
                "priority": "high",
                "tags": ["biology"],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
                "private_path": str(tmp_path),
            }
        ],
    )
    _write_json(
        projects_dir / "project_links.json",
        [
            {
                "id": "available",
                "project_id": "project-1",
                "target_type": "paper",
                "target_id": "paper-1",
                "paper_id": "paper-1",
                "link_type": "key_reference",
                "note": "private link note",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "id": "orphan",
                "project_id": "project-1",
                "target_type": "paper",
                "target_id": "missing-paper",
                "paper_id": "missing-paper",
                "link_type": "related",
                "note": "",
                "created_at": "2026-01-02T00:00:00+00:00",
            },
        ],
    )
    _write_index(
        index_csv,
        [
            {
                "paper_id": "paper-1",
                "filename": "paper.pdf",
                "filepath": str(tmp_path / "private" / "paper.pdf"),
                "title": "Real linked paper",
                "authors": "First Author; Second Author",
                "year": "2025",
                "tags": "one,two",
                "status": "reading",
                "reading_priority": "high",
                "is_archived": "false",
            }
        ],
    )

    detail = project_read_model.build_project_detail(
        "project-1",
        projects_dir=projects_dir,
        index_csv=index_csv,
    )

    assert detail is not None
    assert detail["link_count"] == detail["linked_paper_count"] == 2
    assert detail["orphaned_link_count"] == 1
    assert detail["links"][0]["paper"]["title"] == "Real linked paper"
    assert detail["links"][1]["target_state"] == "orphaned"
    assert "filepath" not in detail["links"][0]["paper"]
    assert "note" not in detail["links"][0]


@pytest.mark.parametrize("filename", ["projects.json", "project_links.json"])
def test_corrupt_project_storage_returns_controlled_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    _write_json(projects_dir / "projects.json", [])
    _write_json(projects_dir / "project_links.json", [])
    (projects_dir / filename).write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(project_read_model, "PROJECTS_DIR", projects_dir)

    response = TestClient(create_app()).get("/projects")

    assert response.status_code == 503
    assert response.json() == {"detail": UNAVAILABLE_DETAIL}
    assert str(tmp_path) not in response.text
    assert "broken" not in response.text


def test_project_gets_do_not_mutate_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_dir = tmp_path / "projects"
    _write_json(
        projects_dir / "projects.json",
        [
            {
                "id": "project-1",
                "name": "Read Only",
                "description": "",
                "status": "active",
                "priority": "normal",
                "tags": [],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    )
    _write_json(projects_dir / "project_links.json", [])
    before = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in projects_dir.iterdir()
    }
    monkeypatch.setattr(project_read_model, "PROJECTS_DIR", projects_dir)

    client = TestClient(create_app())
    assert client.get("/projects").status_code == 200
    assert client.get("/projects/project-1").status_code == 200

    after = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in projects_dir.iterdir()
    }
    assert after == before


def test_tag_read_model_supports_primary_empty_and_legacy_fallback(tmp_path: Path) -> None:
    primary_dir = tmp_path / "primary"
    _write_tag_book(primary_dir, [])
    primary, primary_fallback = tag_read_model.build_canonical_tag_items(
        tag_book_dir=primary_dir,
    )

    fallback_dir = tmp_path / "fallback"
    rules = tmp_path / "tag_rules.json"
    registry = tmp_path / "canonical_tags.json"
    _write_json(rules, {"legacy-tag": {"aliases": ["legacy alias"], "weight": 4}})
    _write_json(
        registry,
        {
            "legacy-tag": {
                "label": "Legacy Tag",
                "category": "concept",
                "aliases": ["old label"],
                "status": "active",
            }
        },
    )
    fallback, loaded_from_fallback = tag_read_model.build_canonical_tag_items(
        tag_book_dir=fallback_dir,
        legacy_rule_path=rules,
        legacy_canonical_tag_path=registry,
    )

    assert primary == []
    assert primary_fallback is False
    assert loaded_from_fallback is True
    assert fallback == [
        {
            "canonical_key": "legacy-tag",
            "label": "Legacy Tag",
            "category": "concept",
            "aliases": ["legacy alias", "old label"],
            "status": "active",
            "suggestion_strength": 4,
        }
    ]


def test_candidate_summary_is_derived_from_existing_paper_data(tmp_path: Path) -> None:
    tag_dir = tmp_path / "tag_book"
    index_csv = tmp_path / "paper_index.csv"
    _write_tag_book(
        tag_dir,
        [
            {
                "canonical": "biology",
                "label": "Biology",
                "category": "field",
                "aliases": ["biology"],
                "status": "active",
                "suggestion_strength": 5,
            }
        ],
    )
    _write_json(
        tag_dir / "method_lexicon.json",
        {
            "entries": [
                {
                    "display": "CRISPR screen",
                    "canonical": "crispr-screen",
                    "category": "method",
                    "aliases": ["CRISPR screen"],
                    "suggestion_strength": 6,
                    "confidence": 0.74,
                }
            ]
        },
    )
    _write_index(
        index_csv,
        [
            {
                "paper_id": "paper-1",
                "filename": "paper.pdf",
                "title": "A CRISPR screen for biology",
                "abstract": "Biology study using a CRISPR screen.",
                "tags": "",
            }
        ],
    )

    summary = tag_read_model.build_candidate_summary(
        tag_book_dir=tag_dir,
        index_csv=index_csv,
    )

    assert summary["availability"] == "available"
    assert summary["state"] == "populated"
    assert summary["evaluated_paper_count"] == 1
    assert summary["candidate_count"] == 1
    assert summary["known_canonical_match_count"] == 1
    assert sum(summary["quality_counts"].values()) == 1


def test_candidate_summary_is_explicitly_unavailable_without_source(tmp_path: Path) -> None:
    tag_dir = tmp_path / "tag_book"
    _write_tag_book(tag_dir, [])

    summary = tag_read_model.build_candidate_summary(
        tag_book_dir=tag_dir,
        index_csv=tmp_path / "missing.csv",
    )

    assert summary == candidate_summary(available=False) | {
        "state": "unavailable",
        "candidate_count": 0,
        "known_canonical_match_count": 0,
        "quality_counts": {"high": 0, "medium": 0, "weak": 0, "rejected": 0},
    }


def test_corrupt_tag_book_returns_controlled_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tag_dir = tmp_path / "tag_book"
    tag_dir.mkdir()
    (tag_dir / "tag_book.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(tag_book, "DEFAULT_TAG_BOOK_DIR", tag_dir)

    response = TestClient(create_app()).get("/tags")

    assert response.status_code == 503
    assert response.json() == {"detail": UNAVAILABLE_DETAIL}
    assert str(tmp_path) not in response.text
    assert "broken" not in response.text


def test_tag_gets_do_not_mutate_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tag_dir = tmp_path / "tag_book"
    index_csv = tmp_path / "paper_index.csv"
    _write_tag_book(
        tag_dir,
        [
            {
                "canonical": "tag",
                "label": "Tag",
                "category": "other",
                "aliases": [],
                "status": "active",
                "suggestion_strength": 1,
            }
        ],
    )
    _write_index(index_csv, [])
    before = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in tag_dir.iterdir()
    }
    monkeypatch.setattr(tag_book, "DEFAULT_TAG_BOOK_DIR", tag_dir)
    monkeypatch.setattr(tag_read_model, "INDEX_CSV", index_csv)

    client = TestClient(create_app())
    assert client.get("/tags").status_code == 200
    assert client.get("/tags/summary").status_code == 200

    after = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in tag_dir.iterdir()
    }
    assert after == before


def test_openapi_documents_all_new_get_contracts() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    assert paths["/projects"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PaginatedProjectList")
    assert paths["/projects/{project_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ProjectDetail")
    assert paths["/projects/{project_id}"]["get"]["responses"]["404"]["content"]["application/json"]["schema"]["$ref"].endswith("/APIError")
    assert paths["/tags"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PaginatedTagList")
    assert paths["/tags/summary"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/CandidateSummaryResponse")
    assert set(paths["/projects"]) == {"get", "post"}
    assert set(paths["/projects/{project_id}"]) == {"get", "patch"}
    assert set(paths["/projects/{project_id}/archive"]) == {"post"}
    assert set(paths["/projects/{project_id}/paper-links"]) == {"post"}
    assert set(paths["/projects/{project_id}/paper-links/{link_id}"]) == {"delete"}
    assert set(paths["/tags"]) == {"get"}
    assert set(paths["/tags/summary"]) == {"get"}
