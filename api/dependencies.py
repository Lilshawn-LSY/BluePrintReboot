from __future__ import annotations

from api.pdf_files import ManagedPdfResult, resolve_managed_pdf
from services import (
    library_read_model,
    note_block_read_model,
    project_read_model,
    settings_read_model,
    tag_read_model,
)
from services.library_read_model import HealthSummary, LibraryStatus, PaperDetail, PaperListItem, ReaderSnapshot
from services.full_text_workflow import FullTextService
from services.note_block_commands import NoteBlockCommandService
from services.note_block_read_model import NoteBlockCollection
from services.project_read_model import ProjectDetail, ProjectListItem
from services.project_commands import ProjectCommandService
from services.reader_commands import ReaderCommandService
from services.tag_candidate_review import TagCandidateReviewService
from services.tag_governance import CanonicalTagGovernanceService
from services.metadata_enrichment import MetadataEnrichmentService
from services.pdf_scan_import import PdfScanImportService
from services.paper_removal import PaperRemovalService
from services.settings_read_model import SettingsSummary
from services.tag_read_model import CandidateReviewQueue, CandidateSummary, CanonicalTag


class ReadModelUnavailable(Exception):
    """An expected API boundary error with no private storage details."""


# Reader commands must operate on the same canonical index and note roots that
# back Library detail/list and Reader snapshot reads.  Keeping this explicit
# avoids a second default-path source drifting away from the read model.
_reader_command_service = ReaderCommandService(
    index_csv=library_read_model.INDEX_CSV,
    notes_dir=library_read_model.NOTES_DIR,
)
_metadata_enrichment_service = MetadataEnrichmentService()
_pdf_scan_import_service = PdfScanImportService()
_paper_removal_service = PaperRemovalService(index_csv=library_read_model.INDEX_CSV, papers_dir=library_read_model.PAPERS_DIR)
_project_command_service = ProjectCommandService()
_note_block_command_service = NoteBlockCommandService()
_tag_governance_service = CanonicalTagGovernanceService()
_tag_candidate_review_service = TagCandidateReviewService(
    governance=_tag_governance_service,
    reader_commands=_reader_command_service,
)
_full_text_service = FullTextService()


def get_health_summary() -> HealthSummary:
    try:
        return library_read_model.build_health_summary()
    except Exception:
        raise ReadModelUnavailable from None


def get_library_status() -> LibraryStatus:
    try:
        return library_read_model.build_library_status()
    except Exception:
        raise ReadModelUnavailable from None


def get_paper_list_items() -> list[PaperListItem]:
    try:
        return library_read_model.build_paper_list_items()
    except Exception:
        raise ReadModelUnavailable from None


def get_paper_detail(paper_id: str) -> PaperDetail | None:
    try:
        return library_read_model.build_paper_detail(paper_id)
    except Exception:
        raise ReadModelUnavailable from None


def get_reader_snapshot(paper_id: str) -> ReaderSnapshot | None:
    try:
        return library_read_model.build_reader_snapshot(paper_id)
    except Exception:
        raise ReadModelUnavailable from None


def get_note_block_collection(paper_id: str) -> NoteBlockCollection | None:
    try:
        return note_block_read_model.build_note_block_collection(paper_id)
    except Exception:
        raise ReadModelUnavailable from None


def get_managed_pdf(paper_id: str) -> ManagedPdfResult:
    try:
        return resolve_managed_pdf(paper_id)
    except Exception:
        raise ReadModelUnavailable from None


def get_project_list_items() -> list[ProjectListItem]:
    try:
        return project_read_model.build_project_list_items()
    except Exception:
        raise ReadModelUnavailable from None


def get_project_detail(project_id: str) -> ProjectDetail | None:
    try:
        return project_read_model.build_project_detail(project_id)
    except Exception:
        raise ReadModelUnavailable from None


def get_canonical_tags() -> tuple[list[CanonicalTag], bool]:
    try:
        return tag_read_model.build_canonical_tag_items()
    except Exception:
        raise ReadModelUnavailable from None


def get_candidate_summary() -> CandidateSummary:
    try:
        return tag_read_model.build_candidate_summary()
    except Exception:
        raise ReadModelUnavailable from None


def get_candidate_review_queue() -> CandidateReviewQueue:
    try:
        return tag_read_model.build_candidate_review_queue()
    except Exception:
        raise ReadModelUnavailable from None


def get_settings_summary() -> SettingsSummary:
    try:
        return settings_read_model.build_settings_summary()
    except Exception:
        raise ReadModelUnavailable from None


def get_reader_command_service() -> ReaderCommandService:
    return _reader_command_service


def get_full_text_service() -> FullTextService:
    return _full_text_service


def get_metadata_enrichment_service() -> MetadataEnrichmentService:
    return _metadata_enrichment_service


def get_pdf_scan_import_service() -> PdfScanImportService:
    return _pdf_scan_import_service


def get_paper_removal_service() -> PaperRemovalService:
    return _paper_removal_service


def get_project_command_service() -> ProjectCommandService:
    return _project_command_service


def get_note_block_command_service() -> NoteBlockCommandService:
    return _note_block_command_service


def get_tag_governance_service() -> CanonicalTagGovernanceService:
    return _tag_governance_service


def get_tag_candidate_review_service() -> TagCandidateReviewService:
    return _tag_candidate_review_service
