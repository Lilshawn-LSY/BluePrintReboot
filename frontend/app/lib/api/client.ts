import type { DashboardSnapshot, HealthSummary, LibraryStatus, PaginatedPaperList, PaperDetail } from "./types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_BLUEPRINT_API_BASE_URL || "/api/blueprint").replace(/\/$/, "");

export class ApiClientError extends Error {
  constructor(message: string, public readonly kind: "unavailable" | "not-found" | "error", public readonly status?: number) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers: { Accept: "application/json" }, cache: "no-store" });
  } catch {
    throw new ApiClientError("The local BluePrintReboot API could not be reached.", "unavailable");
  }

  if (!response.ok) {
    if (response.status === 503) throw new ApiClientError("The local BluePrintReboot API is unavailable.", "unavailable", 503);
    if (response.status === 404) throw new ApiClientError("The requested paper was not found.", "not-found", 404);
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
  getDashboard: async (): Promise<DashboardSnapshot> => {
    const [health, library, papers] = await Promise.all([
      request<HealthSummary>("/health"),
      request<LibraryStatus>("/library/status"),
      request<PaginatedPaperList>("/papers?limit=5&offset=0&archive_status=active"),
    ]);
    return { health, library, papers };
  },
};
