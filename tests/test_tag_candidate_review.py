from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import dependencies
from api.main import create_app
from services.reader_commands import ReaderCommandConflict, ReaderCommandService
from services.tag_candidate_review import (
    TagCandidateReviewConflict,
    TagCandidateReviewInvalid,
    TagCandidateReviewService,
    TagCandidateReviewUnavailable,
)
from services.tag_governance import (
    CanonicalTagGovernanceService,
    TagGovernanceConflict,
    TagGovernanceInvalid,
)
from services import tag_book
from storage.index_store import INDEX_COLUMNS, read_index_snapshot, save_index


def _write_tag_book(directory: Path) -> None:
    tag_book.save_tag_book(
        {
            "version": "2",
            "tags": {
                "single-cell-rna-seq": {
                    "canonical": "single-cell-rna-seq",
                    "label": "Single-cell RNA-seq",
                    "category": "assay",
                    "aliases": ["single-cell RNA sequencing", "scRNA-seq"],
                    "status": "active",
                    "suggestion_strength": 9,
                    "description": "Existing assay.",
                    "created_from": "fixture",
                }
            },
        },
        directory,
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "method_lexicon.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "display": "CRISPR screen",
                        "canonical": "crispr-screen",
                        "category": "method",
                        "aliases": ["CRISPR screen"],
                        "suggestion_strength": 6,
                        "confidence": 0.74,
                        "reason": "Fixture method candidate.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (directory / "normalization_rules.json").write_text("{}", encoding="utf-8")
    (directory / "blocked_terms.json").write_text('{"terms": []}', encoding="utf-8")
    (directory / "candidate_patterns.json").write_text('{"patterns": []}', encoding="utf-8")


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path, CanonicalTagGovernanceService, TagCandidateReviewService]:
    tag_book_dir = tmp_path / "config" / "tag_book"
    _write_tag_book(tag_book_dir)
    data_dir = tmp_path / "data"
    notes_dir = tmp_path / "notes"
    data_dir.mkdir()
    notes_dir.mkdir()
    index_csv = data_dir / "paper_index.csv"
    row = {column: "" for column in INDEX_COLUMNS}
    row.update(
        {
            "paper_id": "paper-1",
            "filename": "paper-1.pdf",
            "title": "Single-cell RNA sequencing with a CRISPR screen",
            "abstract": "We performed a CRISPR screen in pooled cells.",
            "tags": "Legacy Manual",
            "status": "reading",
            "reading_priority": "normal",
            "is_archived": "false",
            "note_path": str(notes_dir / "paper-1.md"),
        }
    )
    save_index(pd.DataFrame([row]), index_csv)
    (notes_dir / "paper-1.md").write_text("# Existing Reading Note\n\nUnsaved state is browser-only.\n", encoding="utf-8")
    governance = CanonicalTagGovernanceService(tag_book_dir=tag_book_dir, workspace_root=tmp_path)
    reader = ReaderCommandService(index_csv=index_csv, notes_dir=notes_dir)
    candidates = TagCandidateReviewService(
        index_csv=index_csv,
        notes_dir=notes_dir,
        review_store_path=data_dir / "tag_candidate_reviews.json",
        tag_book_dir=tag_book_dir,
        governance=governance,
        reader_commands=reader,
    )
    return index_csv, notes_dir, tag_book_dir, governance, candidates


def _paper_tags(index_csv: Path) -> str:
    return str(read_index_snapshot(index_csv).iloc[0]["tags"])


def test_canonical_governance_create_metadata_alias_and_deprecation_preserve_papers(tmp_path: Path) -> None:
    index_csv, _notes_dir, _tag_book_dir, governance, _candidates = _workspace(tmp_path)
    before_index = index_csv.read_bytes()
    _items, revision = governance.snapshot()

    created = governance.create_tag(
        label="Spatial Proteomics",
        category="field",
        description="Fixture tag.",
        suggestion_strength=3,
        expected_revision=revision,
    )
    assert created.status == "created"
    assert created.tag["canonical_key"] == "spatial-proteomics"
    with pytest.raises(TagGovernanceInvalid):
        governance.create_tag(
            label="Spatial Proteomics",
            category="field",
            expected_revision=created.registry_revision,
        )

    updated = governance.update_tag(
        "spatial-proteomics",
        changes={"category": "method", "description": "Updated.", "suggestion_strength": 4},
        expected_revision=created.registry_revision,
    )
    assert updated.tag["category"] == "method"
    assert updated.tag["description"] == "Updated."
    aliased = governance.add_alias(
        "spatial-proteomics",
        alias="spatial protein profiling",
        expected_revision=updated.registry_revision,
    )
    assert aliased.tag["aliases"] == ["spatial protein profiling"]
    with pytest.raises(TagGovernanceInvalid):
        governance.add_alias(
            "single-cell-rna-seq",
            alias="spatial protein profiling",
            expected_revision=aliased.registry_revision,
        )
    with pytest.raises(TagGovernanceInvalid):
        governance.create_tag(
            label="Spatial Protein Profiling",
            category="field",
            expected_revision=aliased.registry_revision,
        )

    deprecated = governance.deprecate_tag("spatial-proteomics", expected_revision=aliased.registry_revision)
    assert deprecated.status == "deprecated"
    items, _revision = governance.snapshot()
    assert next(item for item in items if item["canonical_key"] == "spatial-proteomics")["status"] == "deprecated"
    assert index_csv.read_bytes() == before_index
    assert _paper_tags(index_csv) == "Legacy Manual"


def test_governance_stale_revision_does_not_overwrite_newer_registry_state(tmp_path: Path) -> None:
    _index_csv, _notes_dir, _tag_book_dir, governance, _candidates = _workspace(tmp_path)
    _items, stale_revision = governance.snapshot()
    current = governance.update_tag(
        "single-cell-rna-seq",
        changes={"description": "Current value."},
        expected_revision=stale_revision,
    )

    with pytest.raises(TagGovernanceConflict):
        governance.update_tag(
            "single-cell-rna-seq",
            changes={"description": "Stale value."},
            expected_revision=stale_revision,
        )
    assert current.tag["description"] == "Current value."


def test_candidate_generation_is_persisted_review_only_and_known_tags_resolve(tmp_path: Path) -> None:
    index_csv, notes_dir, _tag_book_dir, _governance, candidates = _workspace(tmp_path)
    before_index = index_csv.read_bytes()
    before_note = (notes_dir / "paper-1.md").read_bytes()

    generated = candidates.generate("paper-1")
    known = next(item for item in generated.items if item["normalized_tag"] == "single-cell-rna-seq")
    unresolved = next(item for item in generated.items if item["normalized_tag"] == "crispr-screen")

    assert generated.state == "generated"
    assert known["state"] == "resolved"
    assert known["resolved_canonical"] == "single-cell-rna-seq"
    assert unresolved["state"] == "unresolved"
    assert index_csv.read_bytes() == before_index
    assert (notes_dir / "paper-1.md").read_bytes() == before_note
    assert candidates.collection("paper-1").review_revision == generated.review_revision


def test_candidate_approve_reject_promote_and_explicit_apply_use_reader_command(tmp_path: Path) -> None:
    index_csv, notes_dir, _tag_book_dir, governance, candidates = _workspace(tmp_path)
    generated = candidates.generate("paper-1")
    known = next(item for item in generated.items if item["normalized_tag"] == "single-cell-rna-seq")
    unresolved = next(item for item in generated.items if item["normalized_tag"] == "crispr-screen")
    note_before_review = (notes_dir / "paper-1.md").read_bytes()

    approved = candidates.approve(
        "paper-1",
        known["candidate_id"],
        expected_review_revision=generated.review_revision,
    )
    assert next(item for item in approved.items if item["candidate_id"] == known["candidate_id"])["state"] == "approved"
    assert _paper_tags(index_csv) == "Legacy Manual"
    assert (notes_dir / "paper-1.md").read_bytes() == note_before_review

    rejected = candidates.reject(
        "paper-1",
        unresolved["candidate_id"],
        expected_review_revision=approved.review_revision,
    )
    rejected_item = next(item for item in rejected.items if item["candidate_id"] == unresolved["candidate_id"])
    assert rejected_item["state"] == "rejected"
    with pytest.raises(TagCandidateReviewInvalid):
        candidates.apply(
            "paper-1",
            unresolved["candidate_id"],
            expected_review_revision=rejected.review_revision,
            expected_tags_revision=rejected.tags_revision,
        )
    regenerated = candidates.generate("paper-1")
    assert next(item for item in regenerated.items if item["candidate_id"] == unresolved["candidate_id"])["state"] == "rejected"

    reset = candidates.generate("paper-1", reset_rejections=True)
    unresolved = next(item for item in reset.items if item["normalized_tag"] == "crispr-screen")
    promoted = candidates.promote(
        "paper-1",
        unresolved["candidate_id"],
        expected_review_revision=reset.review_revision,
    )
    promoted_item = next(item for item in promoted.items if item["candidate_id"] == unresolved["candidate_id"])
    assert promoted_item["state"] == "approved"
    assert promoted_item["resolved_canonical"] == "crispr-screen"
    assert governance.resolve("CRISPR screen")["canonical_key"] == "crispr-screen"
    assert _paper_tags(index_csv) == "Legacy Manual"

    known = next(item for item in promoted.items if item["normalized_tag"] == "single-cell-rna-seq")
    applied = candidates.apply(
        "paper-1",
        known["candidate_id"],
        expected_review_revision=promoted.review_revision,
        expected_tags_revision=promoted.tags_revision,
    )
    assert applied.paper_tag_result.status == "saved"
    assert _paper_tags(index_csv) == "Legacy Manual, single-cell-rna-seq"
    repeated = candidates.apply(
        "paper-1",
        known["candidate_id"],
        expected_review_revision=applied.review_revision,
        expected_tags_revision=applied.paper_tag_result.tags_revision,
    )
    assert repeated.paper_tag_result.status == "no_op"
    assert _paper_tags(index_csv) == "Legacy Manual, single-cell-rna-seq"


def test_promotion_resolves_existing_canonical_without_duplicate_and_review_conflicts_are_safe(tmp_path: Path) -> None:
    _index_csv, _notes_dir, _tag_book_dir, governance, candidates = _workspace(tmp_path)
    generated = candidates.generate("paper-1")
    unresolved = next(item for item in generated.items if item["normalized_tag"] == "crispr-screen")
    _items, registry_revision = governance.snapshot()
    governance.create_tag(
        label="CRISPR Screen",
        category="method",
        expected_revision=registry_revision,
    )

    promoted = candidates.promote(
        "paper-1",
        unresolved["candidate_id"],
        expected_review_revision=generated.review_revision,
    )
    assert next(item for item in promoted.items if item["candidate_id"] == unresolved["candidate_id"])["resolved_canonical"] == "crispr-screen"
    assert len([item for item in governance.snapshot()[0] if item["canonical_key"] == "crispr-screen"]) == 1
    with pytest.raises(TagCandidateReviewConflict):
        candidates.reject(
            "paper-1",
            unresolved["candidate_id"],
            expected_review_revision=generated.review_revision,
        )


def test_candidate_apply_propagates_existing_paper_tag_revision_conflicts(tmp_path: Path) -> None:
    index_csv, _notes_dir, _tag_book_dir, _governance, candidates = _workspace(tmp_path)
    generated = candidates.generate("paper-1")
    known = next(item for item in generated.items if item["normalized_tag"] == "single-cell-rna-seq")
    approved = candidates.approve("paper-1", known["candidate_id"], expected_review_revision=generated.review_revision)
    service = ReaderCommandService(index_csv=index_csv, notes_dir=index_csv.parent.parent / "notes")
    service.add_paper_tag("paper-1", "current", approved.tags_revision)

    with pytest.raises(TagCandidateReviewConflict):
        candidates.apply(
            "paper-1",
            known["candidate_id"],
            expected_review_revision=approved.review_revision,
            expected_tags_revision=approved.tags_revision,
        )
    assert _paper_tags(index_csv) == "Legacy Manual, current"


def test_candidate_promotion_rolls_back_canonical_tag_when_review_save_fails(tmp_path: Path, monkeypatch) -> None:
    _index_csv, _notes_dir, tag_book_dir, governance, candidates = _workspace(tmp_path)
    generated = candidates.generate("paper-1")
    unresolved = next(item for item in generated.items if item["normalized_tag"] == "crispr-screen")
    review_before = candidates.review_store_path.read_bytes()
    registry_path = tag_book_dir / "tag_book.json"
    registry_before = registry_path.read_bytes()
    monkeypatch.setattr(
        candidates,
        "_save_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("forced review save failure")),
    )

    with pytest.raises(TagCandidateReviewUnavailable):
        candidates.promote(
            "paper-1",
            unresolved["candidate_id"],
            expected_review_revision=generated.review_revision,
        )

    assert candidates.review_store_path.read_bytes() == review_before
    assert registry_path.read_bytes() == registry_before
    assert governance.resolve("crispr-screen") is None


def test_candidate_apply_rolls_back_paper_and_retries_idempotently_after_review_failure(tmp_path: Path, monkeypatch) -> None:
    index_csv, notes_dir, _tag_book_dir, _governance, candidates = _workspace(tmp_path)
    generated = candidates.generate("paper-1")
    known = next(item for item in generated.items if item["normalized_tag"] == "single-cell-rna-seq")
    approved = candidates.approve(
        "paper-1",
        known["candidate_id"],
        expected_review_revision=generated.review_revision,
    )
    before = {
        index_csv: index_csv.read_bytes(),
        notes_dir / "paper-1.md": (notes_dir / "paper-1.md").read_bytes(),
        candidates.review_store_path: candidates.review_store_path.read_bytes(),
    }
    original_save_context = candidates._save_context
    monkeypatch.setattr(
        candidates,
        "_save_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("forced review save failure")),
    )

    with pytest.raises(TagCandidateReviewUnavailable):
        candidates.apply(
            "paper-1",
            known["candidate_id"],
            expected_review_revision=approved.review_revision,
            expected_tags_revision=approved.tags_revision,
        )

    assert {path: path.read_bytes() for path in before} == before
    monkeypatch.setattr(candidates, "_save_context", original_save_context)
    retried = candidates.apply(
        "paper-1",
        known["candidate_id"],
        expected_review_revision=approved.review_revision,
        expected_tags_revision=approved.tags_revision,
    )
    assert retried.paper_tag_result.status == "saved"
    assert _paper_tags(index_csv) == "Legacy Manual, single-cell-rna-seq"


def test_candidate_and_governance_api_commands_are_explicit_and_bounded(tmp_path: Path) -> None:
    index_csv, _notes_dir, _tag_book_dir, governance, candidates = _workspace(tmp_path)
    app = create_app()
    app.dependency_overrides[dependencies.get_tag_governance_service] = lambda: governance
    app.dependency_overrides[dependencies.get_tag_candidate_review_service] = lambda: candidates
    client = TestClient(app)

    before = index_csv.read_bytes()
    snapshot = client.get("/tags/governance")
    assert snapshot.status_code == 200
    generated = client.post("/papers/paper-1/tag-candidates/generate", json={})
    assert generated.status_code == 200
    assert generated.json()["state"] == "generated"
    assert index_csv.read_bytes() == before

    created = client.post(
        "/tags",
        json={
            "label": "Spatial Proteomics",
            "category": "field",
            "description": "",
            "suggestion_strength": 1,
            "expected_revision": snapshot.json()["registry_revision"],
        },
    )
    assert created.status_code == 200
    assert created.json()["tag"]["canonical_key"] == "spatial-proteomics"
    assert index_csv.read_bytes() == before
