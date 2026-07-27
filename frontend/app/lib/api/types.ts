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

export interface ProjectListItem {
  project_id: string;
  name: string;
  description: string;
  status: string;
  priority: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  link_count: number;
  linked_paper_count: number;
}

export interface LinkedPaperSummary {
  paper_id: string;
  title: string;
  first_author: string;
  year: string;
  status: string;
  priority: string;
  tags: string[];
  archived: boolean;
}

export type ProjectTargetState = "available" | "orphaned" | "unavailable" | "not_applicable";

export interface ProjectLinkTarget {
  link_id: string;
  link_type: string;
  target_type: string;
  target_state: ProjectTargetState;
  paper_id: string;
  created_at: string;
  paper: LinkedPaperSummary | null;
}

export interface ProjectDetail extends ProjectListItem {
  links: ProjectLinkTarget[];
  links_total: number;
  links_limit: number;
  links_offset: number;
  links_has_more: boolean;
  orphaned_link_count: number;
}

export interface PaginatedProjectList {
  items: ProjectListItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface CanonicalTag {
  canonical_key: string;
  label: string;
  category: string;
  aliases: string[];
  status: string;
  suggestion_strength: number;
}

export interface PaginatedTagList {
  items: CanonicalTag[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  source_state: "canonical" | "legacy_fallback";
}

export interface CandidateSummary {
  availability: "available" | "unavailable";
  state: "populated" | "empty" | "unavailable";
  source: "paper_index" | "none";
  evaluated_paper_count: number;
  candidate_count: number;
  known_canonical_match_count: number;
  quality_counts: {
    high: number;
    medium: number;
    weak: number;
    rejected: number;
  };
}

export type SettingsState = "healthy" | "warning" | "unavailable" | "empty";

export interface SettingsWorkspaceResource {
  code: "papers" | "notes" | "projects" | "tags" | "note_blocks" | "project_links";
  label: string;
  state: SettingsState;
  count: number | null;
  summary: string;
}

export interface SettingsIntegrityIssue {
  code: "missing_pdfs" | "unindexed_pdfs" | "orphan_notes" | "orphan_note_blocks" | "orphan_project_links" | "corrupt_json";
  state: "healthy" | "warning" | "unavailable";
  count: number | null;
  severity: "warning" | "error";
  explanation: string;
  next_action: string;
}

export interface SettingsSummary {
  application: {
    state: "healthy";
    product_version: string;
    api_state: "available";
    api_contract_version: string;
    summary: string;
  };
  workspace: {
    state: SettingsState;
    resources: SettingsWorkspaceResource[];
    summary: string;
  };
  data_integrity: {
    state: "healthy" | "warning" | "unavailable";
    issues: SettingsIntegrityIssue[];
    summary: string;
  };
  backup_readiness: {
    state: "healthy" | "warning" | "unavailable";
    snapshot_available: boolean | null;
    last_updated_at: string | null;
    summary: string;
  };
}

export interface DashboardSnapshot {
  health: HealthSummary;
  library: LibraryStatus;
  papers: PaginatedPaperList;
}
