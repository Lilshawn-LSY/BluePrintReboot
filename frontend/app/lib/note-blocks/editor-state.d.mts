import type { EditableNoteBlockContent, NoteBlock, NoteBlockCommandResponse } from "../api/types";
import type { RevisionDraftState } from "../drafts/revision-draft.mjs";

export const NOTE_BLOCK_FIELDS: Array<keyof EditableNoteBlockContent>;
export const EMPTY_NOTE_BLOCK_DRAFT: EditableNoteBlockContent;
export type NoteBlockEditorState = RevisionDraftState<EditableNoteBlockContent> & {
  mode: "create" | "edit";
  blockId: string;
  status: "clean" | "dirty" | "saving" | "saved" | "no_op" | "conflict" | "error";
  message: string;
};
export function editableNoteBlock(block: NoteBlock): EditableNoteBlockContent;
export function changedNoteBlockFields(draft: EditableNoteBlockContent, baseline: EditableNoteBlockContent): Array<keyof EditableNoteBlockContent>;
export function createNoteBlockEditorState(block?: NoteBlock | null, record?: Record<string, unknown> | null, revision?: string): NoteBlockEditorState;
export function applyNoteBlockCommandResult(state: NoteBlockEditorState, response: NoteBlockCommandResponse): NoteBlockEditorState;
export function preserveNoteBlockDraftAfterFailure(state: NoteBlockEditorState, kind: string): NoteBlockEditorState;
