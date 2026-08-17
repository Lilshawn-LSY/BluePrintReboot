from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from api import dependencies
from api.main import create_app
from ingest.crossref import CrossrefLookupError
from services.library_read_model import build_reader_snapshot
from services.metadata_enrichment import LocalPdfEvidence, MetadataEnrichmentService
from services.reader_commands import ReaderCommandService
from services.reading_note_template import render_reading_note_template
from storage.index_store import INDEX_COLUMNS, read_index_snapshot, save_index


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    index_csv = tmp_path / "data" / "paper_index.csv"
    notes_dir = tmp_path / "notes"
    papers_dir = tmp_path / "papers"
    notes_dir.mkdir(parents=True)
    papers_dir.mkdir()
    pdf_path = papers_dir / "paper-1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    record = {column: "" for column in INDEX_COLUMNS}
    record.update(
        {
            "paper_id": "paper-1",
            "filename": pdf_path.name,
            "filepath": str(pdf_path.resolve()),
            "title": "Manual title",
            "authors": "Manual Author",
            "year": "2020",
            "journal": "Manual Journal",
            "doi": "10.1000/manual",
            "abstract": "Manual abstract must remain exact.",
            "keywords": "manual, keywords",
            "status": "reading",
            "reading_priority": "normal",
            "is_archived": "false",
            "note_path": str((notes_dir / "paper-1.md").resolve()),
        }
    )
    save_index(pd.DataFrame([record]), index_csv)
    note = render_reading_note_template(record).replace(
        "## Raw Notes\n",
        "## Raw Notes\n\nExact unsaved-safe stored body.\n",
    )
    (notes_dir / "paper-1.md").write_text(note, encoding="utf-8", newline="")
    return index_csv, notes_dir, papers_dir, record


def _client(
    *,
    index_csv: Path,
    notes_dir: Path,
    papers_dir: Path,
    crossref_lookup,
    fallback_builder,
) -> TestClient:
    application = create_app()
    enrichment = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=index_csv.parent / "extracted_text",
        crossref_lookup=crossref_lookup,
        fallback_builder=fallback_builder,
    )
    reader = ReaderCommandService(index_csv=index_csv, notes_dir=notes_dir)
    application.dependency_overrides[dependencies.get_metadata_enrichment_service] = lambda: enrichment
    application.dependency_overrides[dependencies.get_reader_command_service] = lambda: reader
    return TestClient(application)


def _crossref_candidate(doi: str) -> dict[str, str]:
    assert doi == "10.1000/manual"
    return {
        "title": "Crossref title",
        "authors": "Candidate Author",
        "year": "2025",
        "journal": "Candidate Journal",
        "doi": doi,
        "abstract": "",
        "keywords": "candidate, keywords",
    }


def test_preview_compares_candidates_without_persisting_or_touching_note(tmp_path: Path) -> None:
    index_csv, notes_dir, papers_dir, _record = _workspace(tmp_path)
    client = _client(
        index_csv=index_csv,
        notes_dir=notes_dir,
        papers_dir=papers_dir,
        crossref_lookup=_crossref_candidate,
        fallback_builder=lambda _record: {
            "source": "pdf_profile",
            "field_sources": {"abstract": "pdf_profile"},
            "abstract": "PDF-derived abstract candidate.",
            "diagnostics": ["PDF profile front matter parsed."],
        },
    )
    before = (index_csv.read_bytes(), (notes_dir / "paper-1.md").read_bytes())

    response = client.post("/papers/paper-1/metadata/enrichment-preview", json={})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"paper_id", "metadata_revision", "candidate_sources", "fields", "diagnostics"}
    fields = {field["field"]: field for field in body["fields"]}
    assert fields["title"] == {
        "field": "title",
        "current_value": "Manual title",
        "candidate_value": "Crossref title",
        "source": "Crossref",
        "state": "conflict",
    }
    assert fields["abstract"]["candidate_value"] == "PDF-derived abstract candidate."
    assert fields["abstract"]["source"] == "PDF-derived profile"
    assert fields["abstract"]["state"] == "conflict"
    assert (index_csv.read_bytes(), (notes_dir / "paper-1.md").read_bytes()) == before


def test_pdf_detected_doi_can_drive_crossref_preview_without_saving_the_doi(tmp_path: Path) -> None:
    index_csv, _notes_dir, papers_dir, _record = _workspace(tmp_path)
    dataframe = read_index_snapshot(index_csv)
    dataframe.loc[dataframe["paper_id"] == "paper-1", "doi"] = ""
    save_index(dataframe, index_csv)
    calls: list[str] = []
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=index_csv.parent / "extracted_text",
        local_evidence_resolver=lambda _paper_id, _path: LocalPdfEvidence(
            text="DOI: 10.2000/from-pdf",
            provider="pypdf",
            origin="preview",
        ),
        crossref_lookup=lambda doi: calls.append(doi) or {"title": "Crossref from PDF DOI", "doi": doi},
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )
    before = index_csv.read_bytes()

    preview = service.preview("paper-1")

    fields = {field.field: field for field in preview.fields}
    assert calls == ["10.2000/from-pdf"]
    assert fields["title"].candidate_value == "Crossref from PDF DOI"
    assert fields["doi"].candidate_value == "10.2000/from-pdf"
    assert fields["doi"].source == "Crossref"
    assert fields["doi"].current_value == ""
    assert fields["doi"].state == "available"
    assert any("lookup only" in diagnostic for diagnostic in preview.diagnostics)
    assert index_csv.read_bytes() == before


def test_pdf_detected_doi_remains_an_explicit_candidate_when_crossref_is_offline(tmp_path: Path) -> None:
    index_csv, _notes_dir, papers_dir, _record = _workspace(tmp_path)
    dataframe = read_index_snapshot(index_csv)
    dataframe.loc[dataframe["paper_id"] == "paper-1", "doi"] = ""
    save_index(dataframe, index_csv)
    service = MetadataEnrichmentService(
        index_csv=index_csv,
        papers_dir=papers_dir,
        extracted_text_dir=index_csv.parent / "extracted_text",
        local_evidence_resolver=lambda _paper_id, _path: LocalPdfEvidence(
            text="DOI: 10.2000/from-pdf",
            provider="pypdf",
            origin="preview",
        ),
        crossref_lookup=lambda _doi: (_ for _ in ()).throw(CrossrefLookupError("offline", error_type="network")),
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )

    fields = {field.field: field for field in service.preview("paper-1").fields}

    assert fields["doi"].candidate_value == "10.2000/from-pdf"
    assert fields["doi"].source == "PDF-derived DOI · pypdf fallback"
    assert fields["doi"].state == "available"


def test_selected_partial_apply_preserves_unselected_and_missing_candidate_metadata(tmp_path: Path) -> None:
    index_csv, notes_dir, papers_dir, _record = _workspace(tmp_path)
    client = _client(
        index_csv=index_csv,
        notes_dir=notes_dir,
        papers_dir=papers_dir,
        crossref_lookup=_crossref_candidate,
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )
    preview = client.post("/papers/paper-1/metadata/enrichment-preview", json={}).json()
    fields = {field["field"]: field for field in preview["fields"]}
    assert fields["abstract"]["state"] == "unavailable"
    assert fields["abstract"]["candidate_value"] == ""
    abstract_before = read_index_snapshot(index_csv).iloc[0]["abstract"]

    applied = client.patch(
        "/papers/paper-1/metadata",
        json={
            "changes": {"title": fields["title"]["candidate_value"], "year": fields["year"]["candidate_value"]},
            "expected_revision": preview["metadata_revision"],
        },
    )

    assert applied.status_code == 200
    assert applied.json()["changed_fields"] == ["title", "year"]
    row = read_index_snapshot(index_csv).iloc[0]
    assert row["title"] == "Crossref title"
    assert row["year"] == "2025"
    assert row["authors"] == "Manual Author"
    assert row["abstract"] == abstract_before
    assert row["keywords"] == "manual, keywords"


def test_conflicting_candidate_requires_explicit_selection_and_duplicate_apply_is_a_no_op(tmp_path: Path) -> None:
    index_csv, notes_dir, papers_dir, _record = _workspace(tmp_path)
    client = _client(
        index_csv=index_csv,
        notes_dir=notes_dir,
        papers_dir=papers_dir,
        crossref_lookup=_crossref_candidate,
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )
    preview = client.post("/papers/paper-1/metadata/enrichment-preview", json={}).json()
    assert read_index_snapshot(index_csv).iloc[0]["title"] == "Manual title"

    first = client.patch(
        "/papers/paper-1/metadata",
        json={
            "changes": {"title": "Crossref title"},
            "expected_revision": preview["metadata_revision"],
        },
    )
    assert first.status_code == 200
    assert first.json()["status"] == "saved"
    second = client.patch(
        "/papers/paper-1/metadata",
        json={
            "changes": {"title": "Crossref title"},
            "expected_revision": first.json()["metadata_revision"],
        },
    )
    assert second.status_code == 200
    assert second.json()["status"] == "no_op"


def test_partial_and_offline_provider_results_remain_previewable_without_private_failures(tmp_path: Path) -> None:
    index_csv, notes_dir, papers_dir, _record = _workspace(tmp_path)

    def offline(_doi: str):
        raise CrossrefLookupError("private/local/path must not escape", error_type="network")

    client = _client(
        index_csv=index_csv,
        notes_dir=notes_dir,
        papers_dir=papers_dir,
        crossref_lookup=offline,
        fallback_builder=lambda _record: {
            "source": "arxiv_id",
            "title": "arXiv fallback title",
            "year": "2024",
            "abstract": "",
            "diagnostics": ["arXiv network connection failed: private/local/path"],
        },
    )
    before = index_csv.read_bytes()

    response = client.post("/papers/paper-1/metadata/enrichment-preview", json={})

    assert response.status_code == 200
    body = response.json()
    fields = {field["field"]: field for field in body["fields"]}
    assert fields["title"]["candidate_value"] == "arXiv fallback title"
    assert fields["title"]["source"] == "arXiv"
    assert fields["abstract"]["state"] == "unavailable"
    assert "private/local/path" not in response.text
    assert index_csv.read_bytes() == before


def test_stale_preview_rejects_selected_apply_without_mutating_newer_metadata(tmp_path: Path) -> None:
    index_csv, notes_dir, papers_dir, _record = _workspace(tmp_path)
    client = _client(
        index_csv=index_csv,
        notes_dir=notes_dir,
        papers_dir=papers_dir,
        crossref_lookup=_crossref_candidate,
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )
    preview = client.post("/papers/paper-1/metadata/enrichment-preview", json={}).json()
    newer = client.patch(
        "/papers/paper-1/metadata",
        json={"changes": {"journal": "Newer Journal"}, "expected_revision": preview["metadata_revision"]},
    )
    assert newer.status_code == 200
    before_stale_apply = index_csv.read_bytes()

    stale = client.patch(
        "/papers/paper-1/metadata",
        json={"changes": {"title": "Crossref title"}, "expected_revision": preview["metadata_revision"]},
    )

    assert stale.status_code == 409
    assert stale.json() == {"detail": "The saved Reader state changed. Reload the current version before retrying."}
    assert index_csv.read_bytes() == before_stale_apply


def test_successful_selected_apply_is_visible_after_reader_snapshot_reload(tmp_path: Path) -> None:
    index_csv, notes_dir, papers_dir, _record = _workspace(tmp_path)
    client = _client(
        index_csv=index_csv,
        notes_dir=notes_dir,
        papers_dir=papers_dir,
        crossref_lookup=_crossref_candidate,
        fallback_builder=lambda _record: {"source": "none", "diagnostics": []},
    )
    preview = client.post("/papers/paper-1/metadata/enrichment-preview", json={}).json()
    saved = client.patch(
        "/papers/paper-1/metadata",
        json={"changes": {"title": "Crossref title"}, "expected_revision": preview["metadata_revision"]},
    )
    assert saved.status_code == 200

    reloaded = build_reader_snapshot(
        "paper-1",
        index_csv=index_csv,
        notes_dir=notes_dir,
        workspace_root=tmp_path,
        papers_dir=papers_dir,
        note_blocks_dir=tmp_path / "data" / "note_blocks",
        projects_dir=tmp_path / "data" / "projects",
        extracted_text_dir=tmp_path / "data" / "extracted_text",
        profile_dir=tmp_path / "data" / "paper_profiles",
    )

    assert reloaded is not None
    assert reloaded["editable_metadata"]["title"] == "Crossref title"
