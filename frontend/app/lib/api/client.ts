import type { DashboardSnapshot, EditablePaperMetadata, HealthSummary, LibraryStatus, MetadataCommandResponse, PaginatedPaperList, PaperDetail, ReaderSnapshot, ReadingNoteCommandResponse } from "./types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_BLUEPRINT_API_BASE_URL || "/api/blueprint").replace(/\/$/, "");

export class ApiClientError extends Error {
  constructor(message: string, public readonly kind: "unavailable" | "not-found" | "conflict" | "invalid" | "error", public readonly status?: number) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function request<T>(
  path: string,
  options: { method?: "GET" | "PATCH" | "PUT"; body?: object } = {},
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
    if (response.status === 503) throw new ApiClientError("The local BluePrintReboot API is unavailable.", "unavailable", 503);
    if (response.status === 404) throw new ApiClientError("The requested paper was not found.", "not-found", 404);
    if (response.status === 409) throw new ApiClientError("The saved version changed. Reload the current version before retrying.", "conflict", 409);
    if (response.status === 422) throw new ApiClientError("The submitted Reader data is invalid.", "invalid", 422);
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
  getPapers: (options: { limit?: number; offset?: number; archiveStatus?: "active" | "archived" | "all" } = {}) => {
    const params = new URLSearchParams({
      limit: String(options.limit ?? 20),
      offset: String(options.offset ?? 0),
      archive_status: options.archiveStatus ?? "active",
    });
    return request<PaginatedPaperList>(`/papers?${params}`);
  },
  getPaper: (paperId: string) => request<PaperDetail>(`/papers/${encodeURIComponent(paperId)}`),
  getReaderSnapshot: (paperId: string) => request<ReaderSnapshot>(`/papers/${encodeURIComponent(paperId)}/reader`),
  saveReaderMetadata: (
    paperId: string,
    changes: Partial<EditablePaperMetadata>,
    expectedRevision: string,
  ) => request<MetadataCommandResponse>(
    `/papers/${encodeURIComponent(paperId)}/metadata`,
    { method: "PATCH", body: { changes, expected_revision: expectedRevision } },
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
