export const PROJECT_FIELDS = ["name", "description", "status", "priority", "tags"];

import { createRevisionDraftState } from "../drafts/revision-draft.mjs";

export function editableProjectMetadata(project) {
  return {
    name: project.name,
    description: project.description,
    status: project.status,
    priority: project.priority,
    tags: [...project.tags],
  };
}

function equalField(left, right) {
  return Array.isArray(left) && Array.isArray(right)
    ? JSON.stringify(left) === JSON.stringify(right)
    : left === right;
}

export function changedProjectFields(draft, baseline) {
  return PROJECT_FIELDS.filter((field) => !equalField(draft[field], baseline[field]));
}

export function createProjectEditorState(project, record = null) {
  const metadata = editableProjectMetadata(project);
  const draftState = createRevisionDraftState({
    draft: metadata,
    baseline: metadata,
    revision: project.project_revision,
    record,
  });
  return {
    ...draftState,
    status: "clean",
    message: "",
  };
}

export function applyProjectCommandResult(state, response) {
  const metadata = editableProjectMetadata(response.project);
  return {
    draft: metadata,
    baseline: { ...metadata, tags: [...metadata.tags] },
    revision: response.project.project_revision,
    status: "saved",
    message: response.status === "no_op"
      ? "Project metadata already matched the saved version."
      : "Project metadata saved.",
  };
}

export function preserveProjectDraftAfterFailure(state, kind) {
  return {
    ...state,
    status: kind === "conflict" ? "conflict" : "error",
    message: kind === "conflict"
      ? "The saved Project changed. Your draft is preserved; reload before retrying."
      : "The Project could not be saved. Your draft is preserved; retry when the API is available.",
  };
}

export function resetProjectDraft(state) {
  return {
    ...state,
    draft: { ...state.baseline, tags: [...state.baseline.tags] },
    status: "clean",
    message: "",
  };
}
