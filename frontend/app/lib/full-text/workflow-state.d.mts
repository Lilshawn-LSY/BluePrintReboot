import type { FullTextDocument, FullTextStatus } from "../api/types";

export type FullTextUiPhase = "loading" | "ready" | "working" | "error";

export interface FullTextUiState {
  phase: FullTextUiPhase;
  data: FullTextStatus | FullTextDocument | null;
  content: string;
  viewerOpen: boolean;
  message: string;
}

export type FullTextUiEvent =
  | { type: "status-loading" }
  | { type: "status-loaded"; status: FullTextStatus }
  | { type: "operation-started" }
  | { type: "document-loaded"; document: FullTextDocument; open: boolean }
  | { type: "operation-failed"; message?: string }
  | { type: "viewer-closed" };

export function initialFullTextUiState(): FullTextUiState;
export function transitionFullTextUiState(state: FullTextUiState, event: FullTextUiEvent): FullTextUiState;
