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
