import type { EditableNoteBlockContent, NoteBlock, NoteBlockCommandResponse } from "../api/types";

export type NoteBlockEditorStatus = "clean" | "dirty" | "saving" | "saved" | "no_op" | "conflict" | "error";

export interface NoteBlockEditorState {
  mode: "create" | "edit";
  blockId: string;
  draft: EditableNoteBlockContent;
  baseline: EditableNoteBlockContent;
  status: NoteBlockEditorStatus;
  message: string;
}

export const NOTE_BLOCK_FIELDS: Array<keyof EditableNoteBlockContent>;
export const EMPTY_NOTE_BLOCK_DRAFT: EditableNoteBlockContent;
export function editableNoteBlock(block: NoteBlock): EditableNoteBlockContent;
export function changedNoteBlockFields(
  draft: EditableNoteBlockContent,
  baseline: EditableNoteBlockContent,
): Array<keyof EditableNoteBlockContent>;
export function createNoteBlockEditorState(block?: NoteBlock | null): NoteBlockEditorState;
export function applyNoteBlockCommandResult(
  state: NoteBlockEditorState,
  response: NoteBlockCommandResponse,
): NoteBlockEditorState;
export function preserveNoteBlockDraftAfterFailure(
  state: NoteBlockEditorState,
  kind: string,
): NoteBlockEditorState;
