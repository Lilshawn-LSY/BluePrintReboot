export const NOTE_BLOCK_FIELDS = [
  "block_type",
  "title",
  "text",
  "page",
  "figure",
  "quote",
  "tags",
];

import { createRevisionDraftState } from "../drafts/revision-draft.mjs";

export const EMPTY_NOTE_BLOCK_DRAFT = {
  block_type: "summary",
  title: "",
  text: "",
  page: "",
  figure: "",
  quote: "",
  tags: [],
};

export function editableNoteBlock(block) {
  return {
    block_type: block.block_type,
    title: block.title,
    text: block.text,
    page: block.page,
    figure: block.figure,
    quote: block.quote,
    tags: [...block.tags],
  };
}

function equalField(left, right) {
  return Array.isArray(left) && Array.isArray(right)
    ? JSON.stringify(left) === JSON.stringify(right)
    : left === right;
}

export function changedNoteBlockFields(draft, baseline) {
  return NOTE_BLOCK_FIELDS.filter((field) => !equalField(draft[field], baseline[field]));
}

export function createNoteBlockEditorState(block = null, record = null, revision = "") {
  const baseline = block ? editableNoteBlock(block) : { ...EMPTY_NOTE_BLOCK_DRAFT, tags: [] };
  const draftState = createRevisionDraftState({
    draft: baseline,
    baseline,
    revision,
    record,
  });
  return {
    mode: block ? "edit" : "create",
    blockId: block?.id || "",
    ...draftState,
    status: "clean",
    message: "",
  };
}

export function applyNoteBlockCommandResult(state, response) {
  const baseline = editableNoteBlock(response.block);
  return {
    ...state,
    mode: "edit",
    blockId: response.block.id,
    draft: { ...baseline, tags: [...baseline.tags] },
    baseline: { ...baseline, tags: [...baseline.tags] },
    status: response.status === "no_op" ? "no_op" : "saved",
    message: response.status === "no_op"
      ? "The Note Block already matched the saved version."
      : "Note Block saved.",
  };
}

export function preserveNoteBlockDraftAfterFailure(state, kind) {
  return {
    ...state,
    status: kind === "conflict" ? "conflict" : "error",
    message: kind === "conflict"
      ? "The Note Block collection changed. Your draft is preserved; reload before retrying."
      : "The Note Block could not be saved. Your draft is preserved.",
  };
}
