import type { EditableProjectMetadata, ProjectCommandResponse, ProjectCommandState, ProjectDetail, ProjectListItem } from "../api/types";
import type { RevisionDraftState } from "../drafts/revision-draft.mjs";

export const PROJECT_FIELDS: Array<keyof EditableProjectMetadata>;
export type ProjectEditorState = RevisionDraftState<EditableProjectMetadata> & {
  status: "clean" | "dirty" | "saving" | "saved" | "conflict" | "error";
  message: string;
};
export function editableProjectMetadata(project: ProjectDetail | ProjectCommandState | ProjectListItem): EditableProjectMetadata;
export function changedProjectFields(draft: EditableProjectMetadata, baseline: EditableProjectMetadata): Array<keyof EditableProjectMetadata>;
export function createProjectEditorState(project: ProjectDetail | ProjectCommandState | ProjectListItem, record?: Record<string, unknown> | null): ProjectEditorState;
export function applyProjectCommandResult(state: ProjectEditorState, response: ProjectCommandResponse): ProjectEditorState;
export function preserveProjectDraftAfterFailure(state: ProjectEditorState, kind: string): ProjectEditorState;
export function resetProjectDraft(state: ProjectEditorState): ProjectEditorState;
