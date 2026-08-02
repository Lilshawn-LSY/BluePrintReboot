import assert from "node:assert/strict";
import test from "node:test";

import {
  applyNoteBlockCommandResult,
  changedNoteBlockFields,
  createNoteBlockEditorState,
  preserveNoteBlockDraftAfterFailure,
} from "../app/lib/note-blocks/editor-state.mjs";

const block = {
  id: "block-1",
  paper_id: "paper-1",
  block_type: "claim",
  title: "Claim",
  text: "Stored text",
  page: "4",
  figure: "Figure 1",
  quote: "Stored quote",
  tags: ["one"],
  created_at: "2026-08-02T00:00:00+00:00",
  updated_at: "2026-08-02T00:00:00+00:00",
};

test("create and edit drafts are Paper-local and changed fields are exact", () => {
  const create = createNoteBlockEditorState();
  const edit = createNoteBlockEditorState(block);
  edit.draft.text = "Unsaved text";
  edit.draft.tags = ["one", "two"];

  assert.equal(create.mode, "create");
  assert.equal(edit.blockId, "block-1");
  assert.deepEqual(changedNoteBlockFields(edit.draft, edit.baseline), ["text", "tags"]);
  assert.equal(create.draft.text, "");
});

test("command success advances the authoritative baseline and reports no-op truthfully", () => {
  const state = createNoteBlockEditorState(block);
  state.draft.text = "Saved text";
  const response = {
    status: "no_op",
    block: { ...block, text: "Saved text" },
    note_blocks_revision: "a".repeat(64),
    total: 1,
  };

  const updated = applyNoteBlockCommandResult(state, response);

  assert.equal(updated.status, "no_op");
  assert.equal(updated.draft.text, "Saved text");
  assert.deepEqual(changedNoteBlockFields(updated.draft, updated.baseline), []);
  assert.match(updated.message, /already matched/);
});

test("conflict and offline failures preserve the exact Note Block draft", () => {
  const state = createNoteBlockEditorState(block);
  state.draft.text = "Exact private draft";

  const conflict = preserveNoteBlockDraftAfterFailure(state, "conflict");
  const offline = preserveNoteBlockDraftAfterFailure(state, "unavailable");

  assert.equal(conflict.status, "conflict");
  assert.equal(conflict.draft.text, "Exact private draft");
  assert.equal(offline.status, "error");
  assert.equal(offline.draft.text, "Exact private draft");
  assert.doesNotMatch(conflict.message, /saved/i);
});
