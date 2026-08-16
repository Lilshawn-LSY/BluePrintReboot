import assert from "node:assert/strict";
import test from "node:test";

import {
  applyMetadataEnrichmentCommandResult,
  applyMetadataCommandResult,
  applyPaperTagCommandResult,
  changedMetadataFields,
  createReaderEditorState,
  deriveEditorStatus,
  refreshDirtyDraftHeader,
  shouldWarnBeforeReplacement,
} from "../app/lib/reader/editor-state.mjs";

const metadata = {
  title: "Paper A",
  authors: "Author One; Author Two",
  year: "2026",
  journal: "Journal",
  doi: "10.1000/a",
  abstract: "Abstract",
  keywords: "one, two",
};

function snapshot(paperId = "paper-a", tags = ["reader"]) {
  const content = [
    "# BluePrint Reading Note",
    "",
    "template_version: 1.0",
    `paper_id: ${paperId}`,
    `title: ${metadata.title}`,
    "tags: reader",
    "",
    "## Raw Notes",
    "",
    `Saved body for ${paperId}`,
    "",
  ].join("\n");
  return {
    paper: { paper_id: paperId, tags },
    editable_metadata: { ...metadata },
    metadata_revision: "a".repeat(64),
    tags_revision: "e".repeat(64),
    saved_note_content: content,
    saved_note_baseline: { exists: true, sha256: "b".repeat(64), size_bytes: content.length },
  };
}

test("metadata and Reading Note dirty states remain independent", () => {
  const state = createReaderEditorState(snapshot());
  state.metadata.draft.title = "Metadata draft";
  assert.deepEqual(changedMetadataFields(state.metadata.draft, state.metadata.baseline), ["title"]);
  assert.equal(deriveEditorStatus(state.note.draft, state.note.baseline), "clean");

  state.note.draft += "Unsaved note";
  state.metadata.draft = { ...state.metadata.baseline };
  assert.deepEqual(changedMetadataFields(state.metadata.draft, state.metadata.baseline), []);
  assert.equal(deriveEditorStatus(state.note.draft, state.note.baseline), "dirty");
});

test("canonical header refresh retains the exact dirty note section body", () => {
  const oldContent = snapshot().saved_note_content;
  const dirty = oldContent.replace("Saved body for paper-a", "Exact dirty body  \nSecond line");
  const persisted = oldContent.replace("title: Paper A", "title: Updated title");

  const result = refreshDirtyDraftHeader(dirty, persisted);

  assert.equal(result.changed, true);
  assert.match(result.content, /title: Updated title/);
  assert.match(result.content, /Exact dirty body  \nSecond line/);
});

test("metadata success advances the note hash without erasing a dirty draft", () => {
  const state = createReaderEditorState(snapshot());
  state.note.draft = state.note.draft.replace("Saved body for paper-a", "Private unsaved body");
  const persisted = state.note.baseline.replace("title: Paper A", "title: Updated title");
  const response = {
    status: "saved",
    metadata: { ...metadata, title: "Updated title" },
    metadata_revision: "c".repeat(64),
    changed_fields: ["title"],
    note_header_status: "updated",
    canonical_note_header: {},
    canonical_note_header_text: persisted.slice(0, persisted.indexOf("## ")),
    reading_note: {
      exists: true,
      content: persisted,
      sha256: "d".repeat(64),
      size_bytes: persisted.length,
    },
  };

  const updated = applyMetadataCommandResult(state, response);

  assert.equal(updated.metadata.status, "saved");
  assert.equal(updated.note.status, "dirty");
  assert.equal(updated.note.sha256, "d".repeat(64));
  assert.match(updated.note.draft, /title: Updated title/);
  assert.match(updated.note.draft, /Private unsaved body/);
  assert.doesNotMatch(updated.note.baseline, /Private unsaved body/);
});

test("metadata success refreshes a canonical dirty draft even when no note exists yet", () => {
  const state = createReaderEditorState(snapshot());
  state.note.baseline = "";
  state.note.draft = state.note.draft.replace("Saved body for paper-a", "Unsaved absent-note body");
  state.note.exists = false;
  const response = {
    status: "saved",
    metadata: { ...metadata, title: "Updated absent title" },
    metadata_revision: "e".repeat(64),
    changed_fields: ["title"],
    note_header_status: "not_present",
    canonical_note_header: {
      template_version: "1.0",
      paper_id: "paper-a",
      title: "Updated absent title",
      doi: "10.1000/a",
      arxiv_id: "",
      year: "2026",
      first_author: "Author One",
      tags: "",
    },
    canonical_note_header_text: [
      "# BluePrint Reading Note",
      "",
      "template_version: 1.0",
      "paper_id: paper-a",
      "title: Updated absent title",
      "doi: 10.1000/a",
      "arxiv_id:",
      "year: 2026",
      "first_author: Author One",
      "tags:",
      "",
    ].join("\n"),
    reading_note: { exists: false, content: "", sha256: "f".repeat(64), size_bytes: 0 },
  };

  const updated = applyMetadataCommandResult(state, response);

  assert.match(updated.note.draft, /title: Updated absent title/);
  assert.match(updated.note.draft, /Unsaved absent-note body/);
  assert.equal(updated.note.baseline, "");
  assert.equal(updated.note.status, "dirty");
});

test("selective enrichment apply preserves unselected manual metadata and dirty Reading Note drafts", () => {
  const state = createReaderEditorState(snapshot());
  state.metadata.draft.authors = "Manual unsaved author";
  state.metadata.draft.keywords = "manual, unsaved";
  state.note.draft = state.note.draft.replace("Saved body for paper-a", "Exact enrichment-note draft");
  const persisted = state.note.baseline.replace("title: Paper A", "title: Candidate title");
  const response = {
    status: "saved",
    metadata: { ...metadata, title: "Candidate title" },
    metadata_revision: "9".repeat(64),
    changed_fields: ["title"],
    note_header_status: "updated",
    canonical_note_header: {},
    canonical_note_header_text: persisted.slice(0, persisted.indexOf("## ")),
    reading_note: {
      exists: true,
      content: persisted,
      sha256: "8".repeat(64),
      size_bytes: persisted.length,
    },
  };

  const updated = applyMetadataEnrichmentCommandResult(state, response, ["title"]);

  assert.equal(updated.metadata.baseline.title, "Candidate title");
  assert.equal(updated.metadata.draft.title, "Candidate title");
  assert.equal(updated.metadata.draft.authors, "Manual unsaved author");
  assert.equal(updated.metadata.draft.keywords, "manual, unsaved");
  assert.equal(updated.metadata.status, "dirty");
  assert.match(updated.metadata.message, /Unselected manual draft fields were kept/);
  assert.equal(updated.note.status, "dirty");
  assert.match(updated.note.draft, /title: Candidate title/);
  assert.match(updated.note.draft, /Exact enrichment-note draft/);
});

test("Paper tag success refreshes the canonical header without erasing a dirty note body", () => {
  const state = createReaderEditorState(snapshot());
  state.note.draft = state.note.draft.replace("Saved body for paper-a", "Private tag-note body");
  state.tags.draft = "new tag";
  const persisted = state.note.baseline.replace("tags:", "tags: reader, new-tag");
  const response = {
    status: "saved",
    tags: ["reader", "new-tag"],
    tags_revision: "f".repeat(64),
    note_header_status: "updated",
    canonical_note_header: {},
    canonical_note_header_text: persisted.slice(0, persisted.indexOf("## ")),
    reading_note: {
      exists: true,
      content: persisted,
      sha256: "1".repeat(64),
      size_bytes: persisted.length,
    },
  };

  const updated = applyPaperTagCommandResult(state, response);

  assert.deepEqual(updated.tags.values, ["reader", "new-tag"]);
  assert.equal(updated.tags.revision, "f".repeat(64));
  assert.equal(updated.tags.status, "saved");
  assert.match(updated.note.draft, /tags: reader, new-tag/);
  assert.match(updated.note.draft, /Private tag-note body/);
  assert.doesNotMatch(updated.note.baseline, /Private tag-note body/);
});

test("Paper tag no-op reports truthfully and keeps the canonical stored tag set", () => {
  const state = createReaderEditorState(snapshot());
  const response = {
    status: "no_op",
    tags: ["reader"],
    tags_revision: "2".repeat(64),
    note_header_status: "unchanged",
    canonical_note_header: {},
    canonical_note_header_text: "",
    reading_note: {
      exists: true,
      content: state.note.baseline,
      sha256: "3".repeat(64),
      size_bytes: state.note.baseline.length,
    },
  };

  const updated = applyPaperTagCommandResult(state, response);

  assert.equal(updated.tags.status, "saved");
  assert.equal(updated.tags.message, "Paper tags already matched the saved version.");
  assert.deepEqual(updated.tags.values, ["reader"]);
});

test("Reader reload initializes Paper tags from the persisted snapshot", () => {
  const reloaded = snapshot("paper-a", ["legacy tag", "persisted-tag"]);
  reloaded.tags_revision = "4".repeat(64);

  const state = createReaderEditorState(reloaded);

  assert.deepEqual(state.tags.values, ["legacy tag", "persisted-tag"]);
  assert.equal(state.tags.revision, "4".repeat(64));
});

test("paper transition state is isolated and dirty replacement requires a warning", () => {
  const paperA = createReaderEditorState(snapshot("paper-a"));
  paperA.note.draft += "Unsaved A";
  assert.equal(
    shouldWarnBeforeReplacement(
      paperA.metadata.draft,
      paperA.metadata.baseline,
      paperA.note.draft,
      paperA.note.baseline,
    ),
    true,
  );

  const paperB = createReaderEditorState(snapshot("paper-b"));
  assert.equal(paperB.paperId, "paper-b");
  assert.doesNotMatch(paperB.note.draft, /Unsaved A/);
  assert.match(paperB.note.draft, /paper-b/);
});

test("conflict and error transient states do not imply fabricated success", () => {
  assert.equal(deriveEditorStatus("draft", "saved", "conflict"), "conflict");
  assert.equal(deriveEditorStatus("draft", "saved", "error"), "error");
  assert.equal(deriveEditorStatus("draft", "saved", "saving"), "saving");
});
