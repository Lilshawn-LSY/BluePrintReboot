import type { CandidateSummary, DashboardSnapshot, EditableNoteBlockContent, EditablePaperMetadata, EditableProjectMetadata, HealthSummary, LibraryStatus, ManagedPdfImportResponse, ManagedPdfScanResponse, MetadataCommandResponse, MetadataEnrichmentPreview, NoteBlockCollection, NoteBlockCommandResponse, NoteBlockLinkCommandResponse, PaginatedPaperList, PaginatedProjectList, PaginatedTagList, PaperDetail, PaperLinkCommandResponse, PaperTagCommandResponse, ProjectCommandResponse, ProjectDetail, ProjectLinkType, ReaderSnapshot, ReadingNoteCommandResponse, SettingsSummary } from "./types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_BLUEPRINT_API_BASE_URL || "/api/blueprint").replace(/\/$/, "");

export class ApiClientError extends Error {
  constructor(message: string, public readonly kind: "unavailable" | "read-model" | "not-found" | "conflict" | "invalid" | "error", public readonly status?: number) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function request<T>(
  path: string,
  options: { method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE"; body?: object; notFoundMessage?: string } = {},
): Promise<T> {
  let response: Response;
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
    });
  } catch {
    throw new ApiClientError("The local BluePrintReboot API could not be reached.", "unavailable");
  }

  if (!response.ok) {
    if (response.status === 503) {
      const failureState = response.headers.get("X-Blueprint-Error-State");
      if (failureState === "api-unavailable") {
        throw new ApiClientError("The local BluePrintReboot API could not be reached.", "unavailable", 503);
      }
      if (failureState === "command-unavailable") {
        throw new ApiClientError("The local command could not be completed. Retry after checking the API.", "error", 503);
      }
      throw new ApiClientError("The local read model could not be read. Check the local data state and retry.", "read-model", 503);
    }
    if (response.status === 404) throw new ApiClientError(options.notFoundMessage ?? "The requested paper was not found.", "not-found", 404);
    if (response.status === 409) throw new ApiClientError("The saved version changed. Reload the current version before retrying.", "conflict", 409);
    if (response.status === 422) throw new ApiClientError("The submitted command data is invalid.", "invalid", 422);
    throw new ApiClientError(`The local API returned HTTP ${response.status}.`, "error", response.status);
  }
  return response.json() as Promise<T>;
}

export function paperPdfUrl(paperId: string): string {
  return `${API_BASE_URL}/papers/${encodeURIComponent(paperId)}/pdf`;
}

export const apiClient = {
  getHealth: () => request<HealthSummary>("/health"),
  getLibraryStatus: () => request<LibraryStatus>("/library/status"),
  scanManagedPdfs: () => request<ManagedPdfScanResponse>("/papers/scan", { method: "POST", body: {} }),
  importManagedPdfs: (relativePaths: string[]) => request<ManagedPdfImportResponse>(
    "/papers/import",
    { method: "POST", body: { relative_paths: relativePaths } },
  ),
  getPapers: (options: { limit?: number; offset?: number; archiveStatus?: "active" | "archived" | "all" } = {}) => {
    const params = new URLSearchParams({
      limit: String(options.limit ?? 20),
      offset: String(options.offset ?? 0),
      archive_status: options.archiveStatus ?? "active",
    });
    return request<PaginatedPaperList>(`/papers?${params}`);
  },
  getPaper: (paperId: string) => request<PaperDetail>(`/papers/${encodeURIComponent(paperId)}`),
  getProjects: (options: { limit?: number; offset?: number } = {}) => {
    const params = new URLSearchParams({
      limit: String(options.limit ?? 20),
      offset: String(options.offset ?? 0),
    });
    return request<PaginatedProjectList>(`/projects?${params}`);
  },
  getProject: (projectId: string, options: { linksLimit?: number; linksOffset?: number } = {}) => {
    const params = new URLSearchParams({
      links_limit: String(options.linksLimit ?? 20),
      links_offset: String(options.linksOffset ?? 0),
    });
    return request<ProjectDetail>(
      `/projects/${encodeURIComponent(projectId)}?${params}`,
      { notFoundMessage: "The requested Project was not found." },
    );
  },
  createProject: (project: EditableProjectMetadata) => request<ProjectCommandResponse>(
    "/projects",
    { method: "POST", body: project },
  ),
  updateProject: (
    projectId: string,
    changes: Partial<EditableProjectMetadata>,
    expectedRevision: string,
  ) => request<ProjectCommandResponse>(
    `/projects/${encodeURIComponent(projectId)}`,
    {
      method: "PATCH",
      body: { changes, expected_revision: expectedRevision },
      notFoundMessage: "The requested Project was not found.",
    },
  ),
  archiveProject: (projectId: string, expectedRevision: string) => request<ProjectCommandResponse>(
    `/projects/${encodeURIComponent(projectId)}/archive`,
    {
      method: "POST",
      body: { expected_revision: expectedRevision },
      notFoundMessage: "The requested Project was not found.",
    },
  ),
  addProjectPaperLink: (
    projectId: string,
    paperId: string,
    linkType: ProjectLinkType,
    expectedLinksRevision: string,
  ) => request<PaperLinkCommandResponse>(
    `/projects/${encodeURIComponent(projectId)}/paper-links`,
    {
      method: "POST",
      body: {
        paper_id: paperId,
        link_type: linkType,
        expected_links_revision: expectedLinksRevision,
      },
      notFoundMessage: "The requested Project or Paper was not found.",
    },
  ),
  removeProjectPaperLink: (
    projectId: string,
    linkId: string,
    expectedLinksRevision: string,
  ) => request<PaperLinkCommandResponse>(
    `/projects/${encodeURIComponent(projectId)}/paper-links/${encodeURIComponent(linkId)}`,
    {
      method: "DELETE",
      body: { expected_links_revision: expectedLinksRevision },
      notFoundMessage: "The requested Project or Paper link was not found.",
    },
  ),
  addProjectNoteBlockLink: (
    projectId: string,
    paperId: string,
    noteBlockId: string,
    linkType: ProjectLinkType,
    expectedLinksRevision: string,
  ) => request<NoteBlockLinkCommandResponse>(
    `/projects/${encodeURIComponent(projectId)}/note-block-links`,
    {
      method: "POST",
      body: {
        paper_id: paperId,
        note_block_id: noteBlockId,
        link_type: linkType,
        expected_links_revision: expectedLinksRevision,
      },
      notFoundMessage: "The requested Project, Paper, or Note Block was not found.",
    },
  ),
  removeProjectNoteBlockLink: (
    projectId: string,
    linkId: string,
    expectedLinksRevision: string,
  ) => request<NoteBlockLinkCommandResponse>(
    `/projects/${encodeURIComponent(projectId)}/note-block-links/${encodeURIComponent(linkId)}`,
    {
      method: "DELETE",
      body: { expected_links_revision: expectedLinksRevision },
      notFoundMessage: "The requested Project or Note Block link was not found.",
    },
  ),
  getTags: (options: { limit?: number; offset?: number } = {}) => {
    const params = new URLSearchParams({
      limit: String(options.limit ?? 20),
      offset: String(options.offset ?? 0),
    });
    return request<PaginatedTagList>(`/tags?${params}`);
  },
  getTagSummary: () => request<CandidateSummary>("/tags/summary"),
  getSettingsSummary: () => request<SettingsSummary>("/settings/summary"),
  getReaderSnapshot: (paperId: string) => request<ReaderSnapshot>(`/papers/${encodeURIComponent(paperId)}/reader`),
  getNoteBlocks: (paperId: string) => request<NoteBlockCollection>(
    `/papers/${encodeURIComponent(paperId)}/note-blocks`,
  ),
  createNoteBlock: (
    paperId: string,
    content: EditableNoteBlockContent,
    expectedRevision: string,
  ) => request<NoteBlockCommandResponse>(
    `/papers/${encodeURIComponent(paperId)}/note-blocks`,
    { method: "POST", body: { ...content, expected_revision: expectedRevision } },
  ),
  updateNoteBlock: (
    paperId: string,
    blockId: string,
    changes: Partial<EditableNoteBlockContent>,
    expectedRevision: string,
  ) => request<NoteBlockCommandResponse>(
    `/papers/${encodeURIComponent(paperId)}/note-blocks/${encodeURIComponent(blockId)}`,
    { method: "PATCH", body: { changes, expected_revision: expectedRevision } },
  ),
  saveReaderMetadata: (
    paperId: string,
    changes: Partial<EditablePaperMetadata>,
    expectedRevision: string,
  ) => request<MetadataCommandResponse>(
    `/papers/${encodeURIComponent(paperId)}/metadata`,
    { method: "PATCH", body: { changes, expected_revision: expectedRevision } },
  ),
  previewMetadataEnrichment: (paperId: string) => request<MetadataEnrichmentPreview>(
    `/papers/${encodeURIComponent(paperId)}/metadata/enrichment-preview`,
    { method: "POST", body: {} },
  ),
  addPaperTag: (
    paperId: string,
    tag: string,
    expectedRevision: string,
  ) => request<PaperTagCommandResponse>(
    `/papers/${encodeURIComponent(paperId)}/tags`,
    { method: "POST", body: { tag, expected_revision: expectedRevision } },
  ),
  removePaperTag: (
    paperId: string,
    tag: string,
    expectedRevision: string,
  ) => request<PaperTagCommandResponse>(
    `/papers/${encodeURIComponent(paperId)}/tags`,
    { method: "DELETE", body: { tag, expected_revision: expectedRevision } },
  ),
  saveReadingNote: (
    paperId: string,
    content: string,
    expectedSha256: string,
  ) => request<ReadingNoteCommandResponse>(
    `/papers/${encodeURIComponent(paperId)}/reading-note`,
    { method: "PUT", body: { content, expected_sha256: expectedSha256 } },
  ),
  getDashboard: async (): Promise<DashboardSnapshot> => {
    const [health, library, papers] = await Promise.all([
      request<HealthSummary>("/health"),
      request<LibraryStatus>("/library/status"),
      request<PaginatedPaperList>("/papers?limit=5&offset=0&archive_status=active"),
    ]);
    return { health, library, papers };
  },
};
