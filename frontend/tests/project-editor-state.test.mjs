import assert from "node:assert/strict";
import test from "node:test";

import {
  applyProjectCommandResult,
  changedProjectFields,
  createProjectEditorState,
  preserveProjectDraftAfterFailure,
  resetProjectDraft,
} from "../app/lib/projects/editor-state.mjs";

const project = {
  project_id: "project-1",
  name: "Baseline",
  description: "Stored",
  status: "active",
  priority: "normal",
  tags: ["one"],
  project_revision: "a".repeat(64),
};

test("creates an independent Project metadata baseline", () => {
  const state = createProjectEditorState(project);
  state.draft.tags.push("draft-only");
  assert.deepEqual(state.baseline.tags, ["one"]);
  assert.equal(state.revision, "a".repeat(64));
});

test("detects only changed allowlisted Project fields", () => {
  const state = createProjectEditorState(project);
  state.draft.name = "Draft";
  state.draft.tags = ["one", "two"];
  assert.deepEqual(changedProjectFields(state.draft, state.baseline), ["name", "tags"]);
});

test("conflicts and offline failures preserve the exact draft and revision", () => {
  const state = createProjectEditorState(project);
  state.draft.description = "Unsaved private draft";
  for (const kind of ["conflict", "unavailable"]) {
    const failed = preserveProjectDraftAfterFailure(state, kind);
    assert.equal(failed.draft.description, "Unsaved private draft");
    assert.equal(failed.baseline.description, "Stored");
    assert.equal(failed.revision, "a".repeat(64));
    assert.match(failed.message, /draft is preserved/i);
  }
});

test("a successful response replaces the baseline and revision honestly", () => {
  const state = createProjectEditorState(project);
  state.draft.name = "Draft";
  const saved = applyProjectCommandResult(state, {
    status: "saved",
    project: {
      ...project,
      name: "Draft",
      project_revision: "b".repeat(64),
    },
  });
  assert.equal(saved.draft.name, "Draft");
  assert.equal(saved.baseline.name, "Draft");
  assert.equal(saved.revision, "b".repeat(64));
  assert.equal(saved.status, "saved");
  assert.deepEqual(changedProjectFields(saved.draft, saved.baseline), []);
});

test("cancel resets the draft without mutating the stored baseline", () => {
  const state = createProjectEditorState(project);
  state.draft.name = "Discard me";
  const reset = resetProjectDraft(state);
  assert.equal(reset.draft.name, "Baseline");
  assert.equal(reset.baseline.name, "Baseline");
  assert.equal(reset.status, "clean");
});
