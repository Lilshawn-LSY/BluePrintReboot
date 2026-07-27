export const METADATA_FIELDS = [
  "title",
  "authors",
  "year",
  "journal",
  "doi",
  "abstract",
  "keywords",
];

export function changedMetadataFields(draft, baseline) {
  return METADATA_FIELDS.filter((field) => draft[field] !== baseline[field]);
}

export function deriveEditorStatus(draft, baseline, transientStatus = "") {
  if (["saving", "saved", "conflict", "error"].includes(transientStatus)) return transientStatus;
  return draft === baseline ? "clean" : "dirty";
}

function sectionStart(text) {
  return String(text).search(/^##\s+/m);
}

export function refreshDirtyDraftHeader(draft, persistedContent) {
  const current = String(draft);
  const persisted = String(persistedContent);
  if (!current.trim() || !persisted.startsWith("# BluePrint Reading Note")) {
    return { content: current, changed: false };
  }
  const currentSection = sectionStart(current);
  const persistedSection = sectionStart(persisted);
  if (
    currentSection < 0
    || !current.slice(0, currentSection).includes("# BluePrint Reading Note")
  ) {
    return { content: current, changed: false };
  }
  const persistedHeader = persistedSection < 0 ? persisted : persisted.slice(0, persistedSection);
  const content = `${persistedHeader.replace(/\s+$/, "")}\n\n${current.slice(currentSection)}`;
  return { content, changed: content !== current };
}

export function shouldWarnBeforeReplacement(metadataDraft, metadataBaseline, noteDraft, noteBaseline) {
  return changedMetadataFields(metadataDraft, metadataBaseline).length > 0 || noteDraft !== noteBaseline;
}

export function createReaderEditorState(snapshot) {
  return {
    paperId: snapshot.paper.paper_id,
    metadata: {
      draft: { ...snapshot.editable_metadata },
      baseline: { ...snapshot.editable_metadata },
      revision: snapshot.metadata_revision,
      status: "clean",
      message: "",
    },
    note: {
      draft: snapshot.saved_note_content,
      baseline: snapshot.saved_note_content,
      sha256: snapshot.saved_note_baseline.sha256,
      exists: snapshot.saved_note_baseline.exists,
      status: "clean",
      message: "",
    },
  };
}

export function applyMetadataCommandResult(state, response) {
  const noteWasDirty = state.note.draft !== state.note.baseline;
  let noteDraft = state.note.draft;
  let headerChanged = false;
  if (noteWasDirty) {
    const headerSource = response.reading_note.exists
      ? response.reading_note.content
      : response.canonical_note_header_text;
    const refreshed = refreshDirtyDraftHeader(noteDraft, headerSource);
    noteDraft = refreshed.content;
    headerChanged = refreshed.changed;
  } else if (response.reading_note.exists) {
      noteDraft = response.reading_note.content;
  }
  const noteBaseline = response.reading_note.exists
    ? response.reading_note.content
    : state.note.baseline;
  const headerNotice = response.note_header_status === "updated"
    ? " Metadata changed the canonical Reading Note header."
    : "";
  return {
    ...state,
    metadata: {
      draft: { ...response.metadata },
      baseline: { ...response.metadata },
      revision: response.metadata_revision,
      status: "saved",
      message: response.status === "no_op"
        ? "Metadata already matched the saved version."
        : `Metadata saved.${headerNotice}`,
    },
    note: {
      ...state.note,
      draft: noteDraft,
      baseline: noteBaseline,
      sha256: response.reading_note.sha256,
      exists: response.reading_note.exists,
      status: noteDraft === noteBaseline ? "clean" : "dirty",
      message: headerChanged
        ? "Metadata changed the canonical header; the unsaved note body was retained."
        : response.note_header_status === "updated"
          ? "Metadata changed the canonical Reading Note header."
          : state.note.message,
    },
  };
}
