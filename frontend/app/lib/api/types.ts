export type HealthState = "healthy" | "degraded" | "blocked" | string;

export interface HealthSummary {
  overall_state: HealthState;
  blocking_issues: number;
  warning_count: number;
  corrupt_critical_state_count: number;
  quarantine_count: number;
  missing_pdf_count: number;
  duplicate_review_count: number;
}

export interface LibraryStatus {
  active_count: number;
  archived_count: number;
  missing_count: number;
  duplicate_count: number;
  corrupt_count: number;
  quarantine_count: number;
  degraded: boolean;
  workspace_warnings: string[];
}

export interface PaperListItem {
  paper_id: string;
  title: string;
  first_author: string;
  year: string;
  status: string;
  priority: string;
  tags: string[];
  archived: boolean;
  missing_pdf: boolean;
  health: string[];
}

export interface ProjectLink {
  project_id: string;
  link_type: string;
  target_type: string;
}

export interface PaperDetail extends PaperListItem {
  authors: string[];
  journal: string;
  abstract: string;
  keywords: string[];
  arxiv_id: string;
  filename: string;
  relative_pdf_path: string;
  doi: string;
  project_links: ProjectLink[];
  note_available: boolean;
  extracted_text_available: boolean;
  profile_available: boolean;
  lifecycle_state: string;
  recoverable_warnings: string[];
}

export type ReaderPdfState = "available" | "missing";

export interface ReaderNoteHeader {
  template_version: string;
  paper_id: string;
  title: string;
  doi: string;
  arxiv_id: string;
  year: string;
  first_author: string;
  tags: string;
}

export interface ReaderNoteBaseline {
  exists: boolean;
  sha256: string;
  size_bytes: number;
}

export interface EditablePaperMetadata {
  title: string;
  authors: string;
  year: string;
  journal: string;
  doi: string;
  abstract: string;
  keywords: string;
}

export interface ReaderSnapshot {
  paper: PaperDetail;
  editable_metadata: EditablePaperMetadata;
  metadata_revision: string;
  pdf_state: ReaderPdfState;
  saved_note_available: boolean;
  saved_note_content: string;
  canonical_note_header: ReaderNoteHeader;
  saved_note_baseline: ReaderNoteBaseline;
  warnings: string[];
  unavailable_reason: string;
}

export interface PersistedReadingNote {
  exists: boolean;
  content: string;
  sha256: string;
  size_bytes: number;
}

export interface MetadataCommandResponse {
  status: "saved" | "no_op";
  metadata: EditablePaperMetadata;
  metadata_revision: string;
  changed_fields: Array<keyof EditablePaperMetadata>;
  note_header_status: "updated" | "unchanged" | "not_present" | "not_required";
  canonical_note_header: ReaderNoteHeader;
  canonical_note_header_text: string;
  reading_note: PersistedReadingNote;
}

export interface ReadingNoteCommandResponse {
  status: "created" | "saved" | "no_op";
  content: string;
  sha256: string;
  size_bytes: number;
}

export interface PaginatedPaperList {
  items: PaperListItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface DashboardSnapshot {
  health: HealthSummary;
  library: LibraryStatus;
  papers: PaginatedPaperList;
}
