import assert from "node:assert/strict";
import test from "node:test";

import {
  beginRevisionSave,
  completeRevisionSave,
  createRevisionDraftState,
  draftStorageKey,
  editRevisionDraft,
  failRevisionSave,
  keepMyRevisionDraft,
  persistRevisionDraft,
  readPersistentRevisionDraft,
  receiveRemoteRevision,
  saveStateLabel,
  applyLatestRevisionDraft,
} from "../app/lib/drafts/revision-draft.mjs";

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

test("local draft remains recoverable through a failed save and a browser reload", () => {
  const storage = memoryStorage();
  const key = draftStorageKey("paper-note", "paper-1");
  let state = createRevisionDraftState({ draft: "server", revision: "r1" });
  state = editRevisionDraft(state, "private draft");
  assert.equal(persistRevisionDraft(storage, key, state), true);

  const started = beginRevisionSave(state);
  const failed = failRevisionSave(started.state, started.request.token, "unavailable", "API unavailable");
  persistRevisionDraft(storage, key, failed);

  const restored = createRevisionDraftState({
    draft: "server",
    revision: "r1",
    record: readPersistentRevisionDraft(storage, key),
  });
  assert.equal(failed.saveState, "offline");
  assert.equal(restored.draft, "private draft");
  assert.equal(restored.baseline, "server");
  assert.equal(restored.saveState, "unsaved");
});

test("starting a save and a server failure never remove the persistent draft", () => {
  const storage = memoryStorage();
  const key = draftStorageKey("paper-note", "paper-5xx");
  let state = editRevisionDraft(createRevisionDraftState({ draft: "saved", revision: "r1" }), "draft before failure");
  persistRevisionDraft(storage, key, state);
  const beforeRequest = storage.getItem(key);
  const started = beginRevisionSave(state);
  persistRevisionDraft(storage, key, started.state);
  assert.equal(storage.getItem(key), beforeRequest, "save start retains the local record");

  state = failRevisionSave(started.state, started.request.token, "error", "HTTP 500");
  persistRevisionDraft(storage, key, state);
  assert.equal(state.saveState, "failed");
  assert.equal(readPersistentRevisionDraft(storage, key).draft, "draft before failure");
});

test("route remount and backend restart recover the same unsaved local draft", () => {
  const storage = memoryStorage();
  const key = draftStorageKey("note-block", "paper-1:block-1");
  const dirty = editRevisionDraft(createRevisionDraftState({ draft: { text: "saved" }, revision: "r1" }), { text: "local work" });
  persistRevisionDraft(storage, key, dirty);

  // A route transition creates a fresh component state. A restarted backend
  // later supplies the same collection revision; neither event owns the draft.
  const remounted = createRevisionDraftState({ draft: { text: "saved" }, revision: "r1", record: readPersistentRevisionDraft(storage, key) });
  const afterRestart = createRevisionDraftState({ draft: { text: "saved" }, revision: "r1", record: readPersistentRevisionDraft(storage, key) });
  assert.deepEqual(remounted.draft, { text: "local work" });
  assert.deepEqual(afterRestart.draft, { text: "local work" });
  assert.equal(afterRestart.saveState, "unsaved");
});

test("a remount retains the local draft while using the newly loaded remote value", () => {
  const storage = memoryStorage();
  const key = draftStorageKey("paper-note", "paper-remote-change");
  const dirty = editRevisionDraft(createRevisionDraftState({ draft: "server A", revision: "r1" }), "local draft");
  persistRevisionDraft(storage, key, dirty);

  const remounted = createRevisionDraftState({
    draft: "server B",
    revision: "r2",
    record: readPersistentRevisionDraft(storage, key),
  });
  assert.equal(remounted.saveState, "changed_elsewhere");
  assert.equal(remounted.draft, "local draft");
  assert.equal(remounted.remote, "server B");
  assert.equal(remounted.remoteRevision, "r2");
});

test("a conflict preserves the exact local draft and separately retains the latest server value", () => {
  let state = createRevisionDraftState({ draft: "server A", revision: "r1" });
  state = editRevisionDraft(state, "my exact draft");
  const started = beginRevisionSave(state);
  state = failRevisionSave(started.state, started.request.token, "conflict");
  state = receiveRemoteRevision(state, {
    value: "server B",
    revision: "r2",
    changedElsewhere: true,
  });

  assert.equal(state.saveState, "changed_elsewhere");
  assert.equal(state.draft, "my exact draft");
  assert.equal(state.remote, "server B");
  assert.equal(applyLatestRevisionDraft(state).draft, "server B");
  const reapply = keepMyRevisionDraft(state);
  assert.equal(reapply.draft, "my exact draft");
  assert.equal(reapply.revision, "r2");
  assert.equal(reapply.saveState, "unsaved");
});

test("a conflicted draft remains recoverable after a browser reload", () => {
  const storage = memoryStorage();
  const key = draftStorageKey("paper-note", "paper-conflict-reload");
  let state = editRevisionDraft(createRevisionDraftState({ draft: "server A", revision: "r1" }), "my draft");
  const started = beginRevisionSave(state);
  state = receiveRemoteRevision(
    failRevisionSave(started.state, started.request.token, "conflict"),
    { value: "server B", revision: "r2", changedElsewhere: true },
  );
  persistRevisionDraft(storage, key, state);

  const restored = createRevisionDraftState({
    draft: "server B",
    revision: "r2",
    record: readPersistentRevisionDraft(storage, key),
  });
  assert.equal(restored.saveState, "changed_elsewhere");
  assert.equal(restored.draft, "my draft");
  assert.equal(restored.remote, "server B");
});

test("only the exact saved snapshot becomes Saved when an edit happens in flight", () => {
  let state = createRevisionDraftState({ draft: "server", revision: "r1" });
  state = editRevisionDraft(state, "draft A");
  const started = beginRevisionSave(state);
  state = editRevisionDraft(started.state, "draft B");
  state = completeRevisionSave(state, started.request.token, { value: "draft A", revision: "r2" });

  assert.equal(state.baseline, "draft A");
  assert.equal(state.draft, "draft B");
  assert.equal(state.revision, "r2");
  assert.equal(state.saveState, "unsaved");
  assert.equal(beginRevisionSave(started.state).request, null, "a second save cannot overlap an active save");
});

test("a confirmed exact snapshot is the only case that clears its local draft record", () => {
  const storage = memoryStorage();
  const key = draftStorageKey("project-metadata", "project-1");
  let state = editRevisionDraft(createRevisionDraftState({ draft: { name: "saved" }, revision: "r1" }), { name: "A" });
  const started = beginRevisionSave(state);
  state = completeRevisionSave(started.state, started.request.token, { value: { name: "A" }, revision: "r2" });
  persistRevisionDraft(storage, key, state);
  assert.equal(state.saveState, "saved");
  assert.equal(storage.getItem(key), null);
});

test("all product save-state labels stay in the compact shared vocabulary", () => {
  assert.deepEqual(
    ["saved", "unsaved", "saving", "failed", "changed_elsewhere", "offline"].map(saveStateLabel),
    ["Saved", "Unsaved changes", "Saving...", "Save failed", "Changed elsewhere", "Offline"],
  );
});
