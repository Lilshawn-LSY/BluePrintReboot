from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import dependencies
from api.main import INVALID_REQUEST_DETAIL, create_app
from api.routes import COMMAND_UNAVAILABLE_DETAIL
from api.schemas import MetadataCommandRequest
from services.paper_metadata_mutation import paper_metadata_revision
from services.reader_commands import (
    EMPTY_NOTE_SHA256,
    ReaderCommandConflict,
    ReaderCommandNotFound,
    ReaderCommandService,
    ReaderCommandUnavailable,
)
from services.reading_note_template import render_reading_note_template
from storage.index_store import INDEX_COLUMNS, save_index
from storage.workspace_lock import workspace_write_lock


def _workspace(
    tmp_path: Path,
    *,
    with_note: bool = True,
    paper_id: str = "paper-1",
) -> tuple[Path, Path, dict[str, str]]:
    index_csv = tmp_path / "data" / "paper_index.csv"
    notes_dir = tmp_path / "notes"
    papers_dir = tmp_path / "papers"
    notes_dir.mkdir(parents=True)
    papers_dir.mkdir()
    pdf_path = papers_dir / f"{paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    record = {column: "" for column in INDEX_COLUMNS}
    record.update(
        {
            "paper_id": paper_id,
            "filename": pdf_path.name,
            "filepath": str(pdf_path.resolve()),
            "title": "Original title",
            "authors": "Author One; Author Two",
            "year": "2025",
            "journal": "Original Journal",
            "doi": "10.1000/original",
            "abstract": "Original abstract",
            "keywords": "one, two",
            "tags": "reader",
            "status": "reading",
            "reading_priority": "normal",
            "is_archived": "false",
            "note_path": str((notes_dir / f"{paper_id}.md").resolve()),
        }
    )
    save_index(pd.DataFrame([record]), index_csv)
    if with_note:
        note = render_reading_note_template(record).replace(
            "## Raw Notes\n",
            "## Raw Notes\n\nExact user body  \nSecond body line\n",
        )
        (notes_dir / f"{paper_id}.md").write_text(note, encoding="utf-8", newline="")
    return index_csv, notes_dir, record


def _service(
    tmp_path: Path,
    *,
    with_note: bool = True,
    paper_id: str = "paper-1",
) -> tuple[ReaderCommandService, Path, Path, dict[str, str]]:
    index_csv, notes_dir, record = _workspace(
        tmp_path,
        with_note=with_note,
        paper_id=paper_id,
    )
    return ReaderCommandService(index_csv=index_csv, notes_dir=notes_dir), index_csv, notes_dir, record


def _client(service: ReaderCommandService) -> TestClient:
    app = create_app()
    app.dependency_overrides[dependencies.get_reader_command_service] = lambda: service
    return TestClient(app)


def test_metadata_revision_is_deterministic_and_excludes_storage_fields() -> None:
    base = {
        "title": " T ",
        "authors": " A ",
        "year": "2026",
        "journal": " J ",
        "doi": "https://doi.org/10.1000/EXAMPLE",
        "abstract": " Abstract ",
        "keywords": " one, two ",
        "filepath": "C:/private/one.pdf",
    }
    changed_private = {**base, "filepath": "D:/other/private.pdf", "paper_id": "other"}

    assert paper_metadata_revision(base) == paper_metadata_revision(changed_private)
    assert paper_metadata_revision(base) != paper_metadata_revision({**base, "title": "Different"})


def test_workspace_lock_is_reentrant_across_reader_write_paths(tmp_path: Path) -> None:
    service, _index, _notes, record = _service(tmp_path)

    with workspace_write_lock(tmp_path):
        metadata = service.save_metadata(
            "paper-1",
            {"title": "Serialized title"},
            paper_metadata_revision(record),
        )
        note = service.save_reading_note(
            "paper-1",
            f"{metadata.reading_note.content}\nSerialized body\n",
            metadata.reading_note.sha256,
        )

    assert metadata.status == "saved"
    assert note.status == "saved"
    assert "Serialized body" in note.content


def test_metadata_schema_rejects_unknown_non_string_year_and_invalid_doi() -> None:
    revision = "a" * 64
    for payload in (
        {"changes": {"tags": "not allowed"}, "expected_revision": revision},
        {"changes": {"year": 2026}, "expected_revision": revision},
        {"changes": {"year": "22"}, "expected_revision": revision},
        {"changes": {"doi": "not-a-doi"}, "expected_revision": revision},
        {"changes": {"title": "x" * 1_001}, "expected_revision": revision},
        {"changes": {}, "expected_revision": revision},
    ):
        with pytest.raises(ValidationError):
            MetadataCommandRequest.model_validate(payload)


def test_metadata_save_normalizes_doi_refreshes_header_and_preserves_body(tmp_path: Path) -> None:
    service, _index, notes, record = _service(tmp_path)
    before = (notes / "paper-1.md").read_text(encoding="utf-8")
    body = before.split("## One-line Summary", 1)[1]

    result = service.save_metadata(
        "paper-1",
        {
            "title": "  Updated title  ",
            "doi": "https://doi.org/10.5555/UPDATED.",
            "journal": "  Updated Journal  ",
        },
        paper_metadata_revision(record),
    )

    assert result.status == "saved"
    assert result.metadata["title"] == "Updated title"
    assert result.metadata["doi"] == "10.5555/updated"
    assert result.changed_fields == ("title", "journal", "doi")
    assert result.note_header_status == "updated"
    assert result.reading_note.content.split("## One-line Summary", 1)[1] == body
    assert "title: Updated title" in result.reading_note.content


def test_metadata_no_op_returns_current_projection_without_writing(tmp_path: Path) -> None:
    service, index_csv, notes, record = _service(tmp_path)
    before = (index_csv.read_bytes(), (notes / "paper-1.md").read_bytes())

    result = service.save_metadata(
        "paper-1",
        {"doi": " DOI: 10.1000/ORIGINAL "},
        paper_metadata_revision(record),
    )

    assert result.status == "no_op"
    assert result.changed_fields == ()
    assert (index_csv.read_bytes(), (notes / "paper-1.md").read_bytes()) == before


def test_stale_metadata_conflict_has_zero_mutation(tmp_path: Path) -> None:
    service, index_csv, notes, _record = _service(tmp_path)
    before = (index_csv.read_bytes(), (notes / "paper-1.md").read_bytes())

    with pytest.raises(ReaderCommandConflict):
        service.save_metadata("paper-1", {"title": "Stale overwrite"}, "0" * 64)

    assert (index_csv.read_bytes(), (notes / "paper-1.md").read_bytes()) == before


def test_metadata_index_failure_is_controlled_and_does_not_touch_note(
    tmp_path: Path, monkeypatch
) -> None:
    service, index_csv, notes, record = _service(tmp_path)
    before = (index_csv.read_bytes(), (notes / "paper-1.md").read_bytes())
    monkeypatch.setattr(
        "services.paper_metadata_mutation.save_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("private index path")),
    )

    with pytest.raises(ReaderCommandUnavailable):
        service.save_metadata(
            "paper-1",
            {"title": "Will fail"},
            paper_metadata_revision(record),
        )

    assert (index_csv.read_bytes(), (notes / "paper-1.md").read_bytes()) == before


def test_metadata_note_failure_rolls_back_index_and_note_exactly(
    tmp_path: Path, monkeypatch
) -> None:
    service, index_csv, notes, record = _service(tmp_path)
    note_path = notes / "paper-1.md"
    before = (index_csv.read_bytes(), note_path.read_bytes())

    def corrupt_then_fail(*_args, **_kwargs):
        note_path.write_text("partial private mutation", encoding="utf-8")
        raise OSError("private note path")

    monkeypatch.setattr(
        "services.paper_metadata_mutation.refresh_note_header",
        corrupt_then_fail,
    )
    with pytest.raises(ReaderCommandUnavailable):
        service.save_metadata(
            "paper-1",
            {"title": "Will roll back"},
            paper_metadata_revision(record),
        )

    assert (index_csv.read_bytes(), note_path.read_bytes()) == before


def test_absent_note_baseline_is_explicit_and_save_creates_canonical_note(
    tmp_path: Path,
) -> None:
    service, _index, notes, _record = _service(tmp_path, with_note=False)

    result = service.save_reading_note(
        "paper-1",
        "User-authored text without a header.",
        EMPTY_NOTE_SHA256,
    )

    assert result.status == "created"
    assert result.sha256 == hashlib.sha256(result.content.encode("utf-8")).hexdigest()
    assert result.size_bytes == len(result.content.encode("utf-8"))
    assert result.content.startswith("# BluePrint Reading Note\n")
    assert result.content.endswith("User-authored text without a header.")
    assert (notes / "paper-1.md").read_text(encoding="utf-8") == result.content


def test_metadata_header_change_does_not_create_an_absent_note(tmp_path: Path) -> None:
    service, _index, notes, record = _service(tmp_path, with_note=False)

    result = service.save_metadata(
        "paper-1",
        {"title": "Updated without a note"},
        paper_metadata_revision(record),
    )

    assert result.status == "saved"
    assert result.note_header_status == "not_present"
    assert result.reading_note.exists is False
    assert result.reading_note.sha256 == EMPTY_NOTE_SHA256
    assert not (notes / "paper-1.md").exists()


def test_metadata_change_canonicalizes_a_noncanonical_persisted_note(
    tmp_path: Path,
) -> None:
    service, _index, notes, record = _service(tmp_path)
    note_path = notes / "paper-1.md"
    note_path.write_text("Legacy exact body  \nSecond line", encoding="utf-8", newline="")

    result = service.save_metadata(
        "paper-1",
        {"title": "Canonicalized title"},
        paper_metadata_revision(record),
    )

    assert result.note_header_status == "updated"
    assert result.reading_note.content.startswith("# BluePrint Reading Note\n")
    assert "title: Canonicalized title" in result.reading_note.content
    assert result.reading_note.content.endswith("Legacy exact body  \nSecond line")
    assert note_path.read_text(encoding="utf-8") == result.reading_note.content


def test_note_save_canonicalizes_header_and_preserves_exact_section_body(
    tmp_path: Path,
) -> None:
    service, _index, notes, _record = _service(tmp_path)
    note_path = notes / "paper-1.md"
    before = note_path.read_text(encoding="utf-8")
    draft = before.replace("title: Original title", "title: stale draft title").replace(
        "Exact user body  \nSecond body line",
        "Edited body with spaces  \nSecond edited line\n",
    )
    expected = hashlib.sha256(before.encode("utf-8")).hexdigest()

    result = service.save_reading_note("paper-1", draft, expected)

    assert result.status == "saved"
    assert "title: Original title" in result.content
    assert "Edited body with spaces  \nSecond edited line\n" in result.content
    assert note_path.read_text(encoding="utf-8") == result.content


def test_note_no_op_and_retry_after_reload_use_current_hash(tmp_path: Path) -> None:
    service, _index, notes, _record = _service(tmp_path)
    current = (notes / "paper-1.md").read_text(encoding="utf-8")
    current_hash = hashlib.sha256(current.encode("utf-8")).hexdigest()

    no_op = service.save_reading_note("paper-1", current, current_hash)
    assert no_op.status == "no_op"

    first = service.save_reading_note("paper-1", f"{current}\nFirst session\n", current_hash)
    with pytest.raises(ReaderCommandConflict):
        service.save_reading_note("paper-1", f"{current}\nStale session\n", current_hash)
    retried = service.save_reading_note(
        "paper-1",
        f"{first.content}\nRetried session\n",
        first.sha256,
    )
    assert retried.status == "saved"
    assert "Retried session" in retried.content


def test_stale_note_conflict_and_save_failure_preserve_persisted_bytes(
    tmp_path: Path, monkeypatch
) -> None:
    service, _index, notes, _record = _service(tmp_path)
    note_path = notes / "paper-1.md"
    before = note_path.read_bytes()
    with pytest.raises(ReaderCommandConflict):
        service.save_reading_note("paper-1", "stale private draft", "0" * 64)
    assert note_path.read_bytes() == before

    monkeypatch.setattr(
        "storage.note_store.atomic_write_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("private failure")),
    )
    with pytest.raises(ReaderCommandUnavailable):
        service.save_reading_note(
            "paper-1",
            "new private draft",
            hashlib.sha256(before).hexdigest(),
        )
    assert note_path.read_bytes() == before


def test_command_api_maps_statuses_and_hides_invalid_private_content(tmp_path: Path) -> None:
    service, index_csv, notes, record = _service(tmp_path)
    client = _client(service)
    revision = paper_metadata_revision(record)
    response = client.patch(
        "/papers/paper-1/metadata",
        json={"changes": {"title": "API title"}, "expected_revision": revision},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert response.json()["canonical_note_header_text"].startswith(
        "# BluePrint Reading Note\n"
    )
    assert set(response.json()["metadata"]) == {
        "title",
        "authors",
        "year",
        "journal",
        "doi",
        "abstract",
        "keywords",
    }

    before = (index_csv.read_bytes(), (notes / "paper-1.md").read_bytes())
    conflict = client.patch(
        "/papers/paper-1/metadata",
        json={"changes": {"title": "private stale draft"}, "expected_revision": revision},
    )
    assert conflict.status_code == 409
    assert "private stale draft" not in conflict.text
    assert (index_csv.read_bytes(), (notes / "paper-1.md").read_bytes()) == before

    invalid = client.put(
        "/papers/paper-1/reading-note",
        json={"content": {"private": "note body"}, "expected_sha256": EMPTY_NOTE_SHA256},
    )
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": INVALID_REQUEST_DETAIL}
    assert "note body" not in invalid.text

    unsupported = client.patch(
        "/papers/paper-1/metadata",
        json={"changes": {"tags": "private unsupported field"}, "expected_revision": "a" * 64},
    )
    assert unsupported.status_code == 422
    assert unsupported.json() == {"detail": INVALID_REQUEST_DETAIL}
    assert "private unsupported field" not in unsupported.text


def test_unknown_paper_is_generic_404(tmp_path: Path) -> None:
    service, _index, _notes, _record = _service(tmp_path)
    client = _client(service)
    response = client.put(
        "/papers/unknown/reading-note",
        json={"content": "draft", "expected_sha256": EMPTY_NOTE_SHA256},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Paper not found."}
    with pytest.raises(ReaderCommandNotFound):
        service.save_metadata("unknown", {"title": "x"}, "0" * 64)


MALICIOUS_PAPER_IDENTITIES = (
    "",
    "../escape",
    "..\\escape",
    "child/note",
    "child\\note",
    "/absolute",
    "C:\\escape",
    "C:/escape",
    "C:escape",
    "\\\\server\\share\\escape",
    ".",
    "..",
    "control\x1fidentity",
)


def _workspace_file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _encoded_path_segment(value: str) -> str:
    return "".join(f"%{byte:02X}" for byte in value.encode("utf-8"))


@pytest.mark.parametrize(
    "paper_id",
    MALICIOUS_PAPER_IDENTITIES,
    ids=(
        "empty",
        "posix-parent",
        "windows-parent",
        "posix-nested",
        "windows-nested",
        "posix-absolute",
        "windows-drive-backslash",
        "windows-drive-slash",
        "windows-drive-relative",
        "windows-unc",
        "dot",
        "dot-dot",
        "control-character",
    ),
)
def test_reader_writes_reject_cross_platform_path_identities_without_mutation_or_disclosure(
    tmp_path: Path,
    paper_id: str,
) -> None:
    service, index_csv, notes, record = _service(tmp_path)
    dataframe = pd.read_csv(index_csv, dtype=str).fillna("")
    dataframe.loc[0, "paper_id"] = paper_id
    save_index(dataframe, index_csv)
    malicious_record = {**record, "paper_id": paper_id}
    before = _workspace_file_bytes(tmp_path)
    private_note_draft = "submitted private Reading Note draft"
    private_metadata_draft = "submitted private metadata draft"

    with pytest.raises(ReaderCommandUnavailable) as note_error:
        service.save_reading_note(paper_id, private_note_draft, EMPTY_NOTE_SHA256)
    with pytest.raises(ReaderCommandUnavailable) as metadata_error:
        service.save_metadata(
            paper_id,
            {"title": private_metadata_draft},
            paper_metadata_revision(malicious_record),
        )
    assert str(note_error.value) == ""
    assert str(metadata_error.value) == ""

    client = _client(service)
    encoded_id = _encoded_path_segment(paper_id)
    responses = (
        client.put(
            f"/papers/{encoded_id}/reading-note",
            json={"content": private_note_draft, "expected_sha256": EMPTY_NOTE_SHA256},
        ),
        client.patch(
            f"/papers/{encoded_id}/metadata",
            json={
                "changes": {"title": private_metadata_draft},
                "expected_revision": paper_metadata_revision(malicious_record),
            },
        ),
    )
    for response in responses:
        assert response.status_code in {404, 503}
        if response.status_code == 503:
            assert response.json() == {"detail": COMMAND_UNAVAILABLE_DETAIL}
        else:
            assert response.json()["detail"] in {"Not Found", "Paper not found."}
        assert private_note_draft not in response.text
        assert private_metadata_draft not in response.text
        assert quote(str(tmp_path)) not in response.text
        assert str(tmp_path) not in response.text

    assert _workspace_file_bytes(tmp_path) == before
    assert (notes / "paper-1.md").is_file()


@pytest.mark.parametrize(
    "paper_id",
    ("paper-1", "example-paper-0123456789", "deep-learning-abcdef1234"),
)
def test_reader_writes_accept_representative_generated_paper_identities(
    tmp_path: Path,
    paper_id: str,
) -> None:
    service, _index_csv, notes, record = _service(tmp_path, paper_id=paper_id)

    metadata = service.save_metadata(
        paper_id,
        {"title": "Updated title"},
        paper_metadata_revision(record),
    )
    note = service.save_reading_note(
        paper_id,
        f"{metadata.reading_note.content}\nAccepted body\n",
        metadata.reading_note.sha256,
    )

    assert metadata.status == "saved"
    assert note.status == "saved"
    assert "Accepted body" in (notes / f"{paper_id}.md").read_text(encoding="utf-8")
