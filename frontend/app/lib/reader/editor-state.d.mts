import type { EditablePaperMetadata, MetadataCommandResponse, PaperTagCommandResponse, ReaderSnapshot } from "../api/types";

export const METADATA_FIELDS: Array<keyof EditablePaperMetadata>;

export function changedMetadataFields(
  draft: EditablePaperMetadata,
  baseline: EditablePaperMetadata,
): Array<keyof EditablePaperMetadata>;

export function deriveEditorStatus(
  draft: string,
  baseline: string,
  transientStatus?: string,
): "clean" | "dirty" | "saving" | "saved" | "conflict" | "error";

export function refreshDirtyDraftHeader(
  draft: string,
  persistedContent: string,
): { content: string; changed: boolean };

export function shouldWarnBeforeReplacement(
  metadataDraft: EditablePaperMetadata,
  metadataBaseline: EditablePaperMetadata,
  noteDraft: string,
  noteBaseline: string,
): boolean;

export interface ReaderEditorState {
  paperId: string;
  metadata: {
    draft: EditablePaperMetadata;
    baseline: EditablePaperMetadata;
    revision: string;
    status: "clean" | "dirty" | "saving" | "saved" | "conflict" | "error";
    message: string;
  };
  tags: {
    values: string[];
    revision: string;
    draft: string;
    status: "clean" | "dirty" | "saving" | "saved" | "conflict" | "error";
    message: string;
  };
  note: {
    draft: string;
    baseline: string;
    sha256: string;
    exists: boolean;
    status: "clean" | "dirty" | "saving" | "saved" | "conflict" | "error";
    message: string;
  };
}

export function createReaderEditorState(snapshot: ReaderSnapshot): ReaderEditorState;
export function applyMetadataCommandResult(
  state: ReaderEditorState,
  response: MetadataCommandResponse,
): ReaderEditorState;
export function applyMetadataEnrichmentCommandResult(
  state: ReaderEditorState,
  response: MetadataCommandResponse,
  selectedFields: Array<keyof EditablePaperMetadata>,
): ReaderEditorState;
export function applyPaperTagCommandResult(
  state: ReaderEditorState,
  response: PaperTagCommandResponse,
): ReaderEditorState;
