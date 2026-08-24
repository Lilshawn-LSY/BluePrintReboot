from __future__ import annotations

import hashlib
import json
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ingest.tag_suggester import apply_paper_text_profile_to_record
from services import tag_book
from services.paper_metadata_mutation import paper_tags_revision
from services.reader_commands import (
    PaperTagCommandResult,
    ReaderCommandConflict,
    ReaderCommandNotFound,
    ReaderCommandService,
    ReaderCommandUnavailable,
)
from services.tag_governance import (
    CanonicalTagGovernanceService,
    TagGovernanceConflict,
    TagGovernanceInvalid,
    TagGovernanceUnavailable,
)
from storage.atomic_text import atomic_write_text
from storage.identities import require_safe_paper_id
from storage.index_store import read_index_snapshot
from storage.paper_profile_store import load_profile
from storage.paths import INDEX_CSV, NOTES_DIR, TAG_CANDIDATE_REVIEWS_JSON
from storage.tag_candidate_review_store import (
    load_tag_candidate_reviews,
    save_tag_candidate_reviews,
)
from storage.workspace_lock import WorkspaceLockUnavailable, workspace_write_lock


CandidateState = Literal["unresolved", "resolved", "approved", "rejected", "applied"]
_TERMINAL_STATES = {"approved", "rejected", "applied"}
MAX_TAG_CANDIDATE_EVIDENCE_SNIPPET_LENGTH = 240
_SNIPPET_ELLIPSIS = "…"


class TagCandidateReviewError(Exception):
    """Base class for controlled candidate-review command failures."""


class TagCandidateReviewConflict(TagCandidateReviewError):
    """The review or Paper-tag revision supplied by the caller is stale."""


class TagCandidateReviewInvalid(TagCandidateReviewError):
    """The requested transition is not allowed by candidate state or tag status."""


class TagCandidateReviewNotFound(TagCandidateReviewError):
    """The Paper or its candidate review item cannot be found."""


class TagCandidateReviewUnavailable(TagCandidateReviewError):
    """Candidate review state or its dependent command could not be completed."""


@dataclass(frozen=True)
class CandidateCollection:
    paper_id: str
    review_revision: str
    tags_revision: str
    state: Literal["not_generated", "generated"]
    items: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class CandidateApplyResult:
    candidate: dict[str, Any]
    review_revision: str
    paper_tag_result: PaperTagCommandResult


@dataclass(frozen=True)
class _FileSnapshot:
    exists: bool
    content: str = ""


def candidate_review_revision(candidates: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        candidates,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_tag_candidate_evidence_snippet(value: object) -> str:
    """Return a deterministic public evidence snippet within the API bound.

    Candidate evidence is sourced from multiple local suggestion inputs and older
    persisted review records predate the public snippet bound.  This boundary is
    deliberately read-safe: it does not change review state or revisions when a
    historical record is merely displayed.
    """

    text = str(value or "")
    if len(text) <= MAX_TAG_CANDIDATE_EVIDENCE_SNIPPET_LENGTH:
        return text

    limit = MAX_TAG_CANDIDATE_EVIDENCE_SNIPPET_LENGTH - len(_SNIPPET_ELLIPSIS)
    prefix = text[:limit]
    # Avoid ending on a combining mark, variation selector, or joiner.  Python
    # string slicing is code-point-safe; this small adjustment avoids the most
    # visible partial Unicode graphemes without changing ordinary snippets.
    while prefix and (
        unicodedata.combining(prefix[-1])
        or prefix[-1] == "\u200d"
        or "VARIATION SELECTOR" in unicodedata.name(prefix[-1], "")
    ):
        prefix = prefix[:-1]
    if not prefix:
        prefix = text[:limit]

    # Prefer a nearby word boundary when it retains useful context.  Scripts
    # without word spaces retain the bounded code-point prefix unchanged.
    boundary = max(prefix.rfind(" "), prefix.rfind("\t"), prefix.rfind("\n"))
    if boundary >= max(0, len(prefix) - 32):
        prefix = prefix[:boundary].rstrip()
    if not prefix:
        prefix = text[:limit]
    return f"{prefix[:limit]}{_SNIPPET_ELLIPSIS}"


def normalize_tag_candidate_evidence(evidence: object) -> list[dict[str, str]]:
    """Allowlist and bound public candidate evidence without mutating storage."""

    if not isinstance(evidence, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "source": str(item.get("source") or ""),
                "source_label": str(item.get("source_label") or item.get("source") or ""),
                "matched_text": str(item.get("matched_text") or ""),
                "snippet": normalize_tag_candidate_evidence_snippet(item.get("snippet")),
            }
        )
    return normalized


class TagCandidateReviewService:
    """Persisted candidate review state, deliberately separate from Paper tag writes."""

    def __init__(
        self,
        *,
        index_csv: Path = INDEX_CSV,
        notes_dir: Path = NOTES_DIR,
        review_store_path: Path = TAG_CANDIDATE_REVIEWS_JSON,
        tag_book_dir: Path = tag_book.DEFAULT_TAG_BOOK_DIR,
        governance: CanonicalTagGovernanceService | None = None,
        reader_commands: ReaderCommandService | None = None,
    ) -> None:
        self.index_csv = Path(index_csv)
        self.notes_dir = Path(notes_dir)
        self.review_store_path = Path(review_store_path)
        self.tag_book_dir = Path(tag_book_dir)
        self.workspace_root = _workspace_root(self.index_csv)
        self.governance = governance or CanonicalTagGovernanceService(
            tag_book_dir=self.tag_book_dir,
            workspace_root=self.workspace_root,
        )
        self.reader_commands = reader_commands or ReaderCommandService(
            index_csv=self.index_csv,
            notes_dir=self.notes_dir,
        )

    def collection(self, paper_id: str) -> CandidateCollection:
        record = self._record(paper_id)
        if record is None:
            raise TagCandidateReviewNotFound
        reviews = self._load_reviews()
        context = reviews["papers"].get(paper_id)
        candidates = list(context.get("candidates", [])) if isinstance(context, dict) else []
        return self._collection_from(record, candidates, generated=context is not None)

    def generate(self, paper_id: str, *, reset_rejections: bool = False) -> CandidateCollection:
        with self._locked():
            record = self._record(paper_id)
            if record is None:
                raise TagCandidateReviewNotFound
            reviews = self._load_reviews()
            previous_context = reviews["papers"].get(paper_id, {})
            previous_items = {
                str(item.get("candidate_id", "")): item
                for item in previous_context.get("candidates", [])
                if isinstance(item, dict)
            }
            generated = self._generated_candidates(record)
            candidates: list[dict[str, Any]] = []
            for item in generated:
                previous = previous_items.get(item["candidate_id"])
                if previous and not reset_rejections and item.get("quality") != "rejected":
                    for key in ("state", "resolved_canonical", "canonical_status"):
                        if key in previous:
                            item[key] = previous[key]
                candidates.append(item)
            reviews["papers"][paper_id] = {"candidates": candidates}
            self._save_reviews(reviews)
            return self._collection_from(record, candidates, generated=True)

    def approve(
        self,
        paper_id: str,
        candidate_id: str,
        *,
        expected_review_revision: str,
    ) -> CandidateCollection:
        with self._locked():
            record, reviews, candidates, index = self._mutable_candidate(
                paper_id,
                candidate_id,
                expected_review_revision,
            )
            candidate = self._resolved_candidate(candidates[index])
            if candidate.get("quality") == "rejected" or candidate.get("state") == "rejected":
                raise TagCandidateReviewInvalid("Rejected candidates cannot be approved.")
            if candidate.get("state") == "applied":
                return self._collection_from(record, candidates, generated=True)
            if not self._is_active_resolution(candidate):
                raise TagCandidateReviewInvalid("Resolve or promote this candidate to an active canonical tag before approval.")
            candidate["state"] = "approved"
            candidates[index] = candidate
            self._save_context(reviews, paper_id, candidates)
            return self._collection_from(record, candidates, generated=True)

    def reject(
        self,
        paper_id: str,
        candidate_id: str,
        *,
        expected_review_revision: str,
    ) -> CandidateCollection:
        with self._locked():
            record, reviews, candidates, index = self._mutable_candidate(
                paper_id,
                candidate_id,
                expected_review_revision,
            )
            candidate = self._resolved_candidate(candidates[index])
            if candidate.get("state") == "applied":
                raise TagCandidateReviewInvalid("Applied candidates cannot be rejected; remove the Paper tag explicitly first if needed.")
            if candidate.get("state") == "rejected":
                return self._collection_from(record, candidates, generated=True)
            candidate["state"] = "rejected"
            candidates[index] = candidate
            self._save_context(reviews, paper_id, candidates)
            return self._collection_from(record, candidates, generated=True)

    def promote(
        self,
        paper_id: str,
        candidate_id: str,
        *,
        expected_review_revision: str,
        label: str | None = None,
        category: str | None = None,
    ) -> CandidateCollection:
        with self._locked():
            snapshots = self._snapshots(
                self.review_store_path,
                self.tag_book_dir / "tag_book.json",
            )
            record, reviews, candidates, index = self._mutable_candidate(
                paper_id,
                candidate_id,
                expected_review_revision,
            )
            candidate = self._resolved_candidate(candidates[index])
            if candidate.get("state") == "rejected" or candidate.get("quality") == "rejected":
                raise TagCandidateReviewInvalid("Rejected candidates cannot be promoted.")
            requested_label = str(label).strip() if label is not None else str(candidate.get("tag_text", "")).strip()
            if not requested_label:
                raise TagCandidateReviewInvalid("A promoted canonical tag needs a label.")
            requested_category = str(category).strip() if category is not None else str(candidate.get("category", "other"))

            resolved = self.governance.resolve(requested_label) or self.governance.resolve(
                str(candidate.get("normalized_tag", ""))
            )
            if resolved is not None:
                if resolved["status"] != "active":
                    raise TagCandidateReviewInvalid("A deprecated canonical tag remains inspectable but cannot be a promotion target.")
                canonical = resolved["canonical_key"]
            else:
                try:
                    _items, registry_revision = self.governance.snapshot()
                    created = self.governance.create_tag(
                        label=requested_label,
                        category=requested_category,
                        expected_revision=registry_revision,
                    )
                    canonical = created.tag["canonical_key"]
                    candidate_identity = tag_book.normalize_tag(candidate.get("tag_text", ""))
                    if candidate_identity and candidate_identity != canonical:
                        self.governance.add_alias(
                            canonical,
                            alias=str(candidate.get("tag_text", "")),
                            expected_revision=created.registry_revision,
                        )
                except (TagGovernanceConflict, TagGovernanceInvalid) as error:
                    self._rollback_or_unavailable(
                        snapshots,
                        TagCandidateReviewInvalid(str(error)),
                    )
                except TagGovernanceUnavailable:
                    self._rollback_or_unavailable(
                        snapshots,
                        TagCandidateReviewUnavailable(),
                    )
            try:
                candidate["resolved_canonical"] = canonical
                candidate["canonical_status"] = "active"
                candidate["state"] = "approved"
                candidates[index] = candidate
                self._save_context(reviews, paper_id, candidates)
                return self._collection_from(record, candidates, generated=True)
            except Exception as exc:
                self._rollback_or_unavailable(snapshots, exc)

    def apply(
        self,
        paper_id: str,
        candidate_id: str,
        *,
        expected_review_revision: str,
        expected_tags_revision: str,
    ) -> CandidateApplyResult:
        with self._locked():
            record, reviews, candidates, index = self._mutable_candidate(
                paper_id,
                candidate_id,
                expected_review_revision,
            )
            candidate = self._resolved_candidate(candidates[index])
            if candidate.get("state") == "rejected":
                raise TagCandidateReviewInvalid("Rejected candidates cannot be applied.")
            if candidate.get("state") not in {"resolved", "approved", "applied"}:
                raise TagCandidateReviewInvalid("Approve or resolve this candidate before applying it to the Paper.")
            if not self._is_active_resolution(candidate):
                raise TagCandidateReviewInvalid("A deprecated or unresolved candidate cannot be applied to a Paper.")
            canonical = str(candidate["resolved_canonical"])
            paper_identity = require_safe_paper_id(record.get("paper_id", ""))
            snapshots = self._snapshots(
                self.review_store_path,
                self.index_csv,
                self.notes_dir / f"{paper_identity}.md",
            )
            try:
                result = self.reader_commands.add_paper_tag(
                    paper_id,
                    canonical,
                    expected_tags_revision,
                )
            except ReaderCommandConflict:
                raise TagCandidateReviewConflict from None
            except ReaderCommandNotFound:
                raise TagCandidateReviewNotFound from None
            except ReaderCommandUnavailable:
                self._rollback_or_unavailable(
                    snapshots,
                    TagCandidateReviewUnavailable(),
                )
            try:
                candidate["state"] = "applied"
                candidates[index] = candidate
                self._save_context(reviews, paper_id, candidates)
                return CandidateApplyResult(
                    candidate=self._public_candidate(candidate),
                    review_revision=candidate_review_revision(candidates),
                    paper_tag_result=result,
                )
            except Exception as exc:
                self._rollback_or_unavailable(snapshots, exc)

    def _mutable_candidate(
        self,
        paper_id: str,
        candidate_id: str,
        expected_review_revision: str,
    ) -> tuple[dict[str, str], dict[str, Any], list[dict[str, Any]], int]:
        record = self._record(paper_id)
        if record is None:
            raise TagCandidateReviewNotFound
        reviews = self._load_reviews()
        context = reviews["papers"].get(paper_id)
        if not isinstance(context, dict):
            raise TagCandidateReviewNotFound
        candidates = list(context.get("candidates", []))
        if candidate_review_revision(candidates) != expected_review_revision:
            raise TagCandidateReviewConflict
        for index, candidate in enumerate(candidates):
            if str(candidate.get("candidate_id", "")) == candidate_id:
                return record, reviews, candidates, index
        raise TagCandidateReviewNotFound

    def _generated_candidates(self, record: dict[str, str]) -> list[dict[str, Any]]:
        suggestion_record = dict(record)
        profile = load_profile(str(record.get("paper_id", "")), self._profile_dir())
        if profile is not None:
            suggestion_record = apply_paper_text_profile_to_record(suggestion_record, profile)
        else:
            preview = self._extracted_text_preview(str(record.get("paper_id", "")))
            if preview:
                suggestion_record["extracted_text_preview"] = preview
        try:
            loaded = tag_book.load_tag_book(self.tag_book_dir)
            suggestions = tag_book.explain_tag_book_suggestions(suggestion_record, loaded)
        except Exception:
            raise TagCandidateReviewUnavailable from None
        return [self._candidate_from_suggestion(record["paper_id"], item) for item in suggestions]

    def _candidate_from_suggestion(self, paper_id: str, suggestion: dict[str, Any]) -> dict[str, Any]:
        normalized = tag_book.normalize_tag(
            suggestion.get("canonical") or suggestion.get("tag") or suggestion.get("display")
        )
        kind = str(suggestion.get("kind", "new_candidate"))
        identifier = hashlib.sha256(f"{paper_id}\0{kind}\0{normalized}".encode("utf-8")).hexdigest()
        resolved = self.governance.resolve(normalized)
        quality = str(suggestion.get("quality", ""))
        if kind == "rejected_candidate" or quality == "rejected":
            state: CandidateState = "rejected"
        elif resolved is not None:
            state = "resolved"
        else:
            state = "unresolved"
        return {
            "candidate_id": identifier,
            "tag_text": str(suggestion.get("display") or normalized),
            "normalized_tag": normalized,
            "resolved_canonical": resolved["canonical_key"] if resolved else "",
            "canonical_status": resolved["status"] if resolved else "",
            "category": str(suggestion.get("category") or "other"),
            "source": str(suggestion.get("source") or ""),
            "source_label": str(suggestion.get("source_label") or suggestion.get("source") or ""),
            "matched_text": str(suggestion.get("matched_text") or ""),
            "evidence": normalize_tag_candidate_evidence(suggestion.get("evidence", [])),
            "score": int(suggestion.get("score", 0) or 0),
            "confidence": float(suggestion.get("confidence", 0.0) or 0.0),
            "quality": quality,
            "reason": str(suggestion.get("reason") or ""),
            "state": state,
            "generated_kind": kind,
        }

    def _collection_from(
        self,
        record: dict[str, str],
        candidates: list[dict[str, Any]],
        *,
        generated: bool,
    ) -> CandidateCollection:
        hydrated = [self._public_candidate(self._resolved_candidate(candidate)) for candidate in candidates]
        return CandidateCollection(
            paper_id=str(record["paper_id"]),
            review_revision=candidate_review_revision(candidates),
            tags_revision=paper_tags_revision(record),
            state="generated" if generated else "not_generated",
            items=tuple(hydrated),
        )

    def _resolved_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        hydrated = dict(candidate)
        if hydrated.get("state") == "rejected":
            return hydrated
        resolved = self.governance.resolve(str(hydrated.get("resolved_canonical") or hydrated.get("normalized_tag") or ""))
        if resolved is not None:
            hydrated["resolved_canonical"] = resolved["canonical_key"]
            hydrated["canonical_status"] = resolved["status"]
            if hydrated.get("state") == "unresolved":
                hydrated["state"] = "resolved"
        return hydrated

    @staticmethod
    def _is_active_resolution(candidate: dict[str, Any]) -> bool:
        return bool(candidate.get("resolved_canonical")) and candidate.get("canonical_status") == "active"

    @staticmethod
    def _public_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "candidate_id",
            "tag_text",
            "normalized_tag",
            "resolved_canonical",
            "canonical_status",
            "category",
            "source",
            "source_label",
            "matched_text",
            "evidence",
            "score",
            "confidence",
            "quality",
            "reason",
            "state",
            "generated_kind",
        )
        public = {key: candidate.get(key) for key in allowed}
        # Historical persisted records can have evidence created before the
        # response-schema limit.  Normalize only the public projection so a
        # read never rewrites user-controlled review data or its revision.
        public["evidence"] = normalize_tag_candidate_evidence(candidate.get("evidence", []))
        return public

    def _record(self, paper_id: str) -> dict[str, str] | None:
        try:
            dataframe = read_index_snapshot(self.index_csv)
            matches = dataframe[dataframe["paper_id"] == paper_id]
        except Exception:
            raise TagCandidateReviewUnavailable from None
        if matches.empty:
            return None
        return {str(key): str(value) for key, value in matches.iloc[0].fillna("").to_dict().items()}

    def _load_reviews(self) -> dict[str, Any]:
        try:
            return load_tag_candidate_reviews(self.review_store_path)
        except Exception:
            raise TagCandidateReviewUnavailable from None

    def _save_reviews(self, reviews: dict[str, Any]) -> None:
        try:
            save_tag_candidate_reviews(reviews, self.review_store_path)
        except Exception:
            raise TagCandidateReviewUnavailable from None

    def _save_context(self, reviews: dict[str, Any], paper_id: str, candidates: list[dict[str, Any]]) -> None:
        reviews["papers"][paper_id] = {"candidates": candidates}
        self._save_reviews(reviews)

    @contextmanager
    def _locked(self):
        try:
            with workspace_write_lock(self.workspace_root):
                yield
        except WorkspaceLockUnavailable:
            raise TagCandidateReviewUnavailable from None

    def _profile_dir(self) -> Path:
        return self.index_csv.parent / "paper_profiles"

    def _extracted_text_preview(self, paper_id: str) -> str:
        try:
            safe_paper_id = require_safe_paper_id(paper_id)
        except ValueError:
            return ""
        path = self.index_csv.parent / "extracted_text" / f"{safe_paper_id}.txt"
        try:
            return path.read_text(encoding="utf-8")[:5000] if path.is_file() else ""
        except OSError:
            return ""

    @staticmethod
    def _snapshots(*paths: Path) -> dict[Path, _FileSnapshot]:
        snapshots: dict[Path, _FileSnapshot] = {}
        for path in paths:
            target = Path(path)
            snapshots[target] = (
                _FileSnapshot(True, target.read_text(encoding="utf-8"))
                if target.is_file()
                else _FileSnapshot(False)
            )
        return snapshots

    @staticmethod
    def _restore_snapshots(snapshots: dict[Path, _FileSnapshot]) -> None:
        failures = 0
        for path, snapshot in snapshots.items():
            try:
                if snapshot.exists:
                    atomic_write_text(path, snapshot.content)
                elif path.exists():
                    path.unlink()
            except Exception:
                failures += 1
        if failures:
            raise TagCandidateReviewUnavailable

    def _rollback_or_unavailable(
        self,
        snapshots: dict[Path, _FileSnapshot],
        original_error: Exception,
    ) -> None:
        try:
            self._restore_snapshots(snapshots)
        except Exception:
            raise TagCandidateReviewUnavailable from original_error
        if isinstance(original_error, TagCandidateReviewError):
            raise original_error
        raise TagCandidateReviewUnavailable from original_error


def _workspace_root(index_csv: Path) -> Path:
    path = Path(index_csv).resolve(strict=False)
    return path.parent.parent if path.parent.name.casefold() == "data" else path.parent
