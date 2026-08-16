"use client";

import { ArrowLeft, RotateCcw, Save } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { PdfJsReader } from "../components/PdfJsReader";
import { NoteBlocksWorkspace } from "../components/NoteBlocksWorkspace";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";
import type { EditablePaperMetadata, MetadataEnrichmentPreview, ReaderSnapshot } from "../lib/api/types";
import {
  applyMetadataEnrichmentCommandResult,
  applyMetadataCommandResult,
  applyPaperTagCommandResult,
  changedMetadataFields,
  createReaderEditorState,
  refreshDirtyDraftHeader,
  shouldWarnBeforeReplacement,
} from "../lib/reader/editor-state.mjs";


type EditorStatus = "clean" | "dirty" | "saving" | "saved" | "conflict" | "error";
type EnrichmentStatus = "idle" | "loading" | "ready" | "saving" | "saved" | "conflict" | "error";

type EnrichmentState = {
  status: EnrichmentStatus;
  preview: MetadataEnrichmentPreview | null;
  selectedFields: Array<keyof EditablePaperMetadata>;
  message: string;
};

const FIELD_LABELS: Record<keyof EditablePaperMetadata, string> = {
  title: "Title",
  authors: "Authors",
  year: "Year",
  journal: "Journal",
  doi: "DOI",
  abstract: "Abstract",
  keywords: "Keywords",
};

const CANDIDATE_STATE_LABELS = {
  unchanged: "Unchanged",
  conflict: "Conflicts with current",
  available: "Candidate available",
  unavailable: "Unavailable",
} as const;


function ReaderPdf({ snapshot }: { snapshot: ReaderSnapshot }) {
  if (snapshot.pdf_state === "missing" || snapshot.paper.missing_pdf || !snapshot.paper.relative_pdf_path) {
    return (
      <EmptyState
        title="Managed PDF missing"
        description={snapshot.unavailable_reason || "This paper record does not currently have an accessible PDF in the managed library."}
      />
    );
  }
  return <PdfJsReader paperId={snapshot.paper.paper_id} />;
}


function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}


function errorState(error: unknown): { status: EditorStatus; message: string } {
  if (error instanceof ApiClientError && error.kind === "conflict") {
    return { status: "conflict", message: "The saved version changed. Your draft is still here; reload the current version before retrying." };
  }
  if (error instanceof ApiClientError && error.kind === "invalid") {
    return { status: "error", message: "The draft was not accepted. Check the field values; nothing was saved." };
  }
  return { status: "error", message: "Save failed. Your draft remains unchanged." };
}


function enrichmentStateForError(error: unknown, action: "fetch" | "apply"): Pick<EnrichmentState, "status" | "message"> {
  if (error instanceof ApiClientError && error.kind === "conflict") {
    return {
      status: "conflict",
      message: "The saved metadata changed. Your candidate preview and selected fields are still here; reload candidates before retrying.",
    };
  }
  return {
    status: "error",
    message: action === "fetch"
      ? "Candidates could not be retrieved. No metadata was changed."
      : "Selected metadata could not be saved. Your candidate selection and editor drafts remain unchanged.",
  };
}


function refreshedCandidatePreview(
  preview: MetadataEnrichmentPreview,
  metadata: EditablePaperMetadata,
  revision: string,
): MetadataEnrichmentPreview {
  return {
    ...preview,
    metadata_revision: revision,
    fields: preview.fields.map((field) => {
      const currentValue = metadata[field.field];
      const state = !field.candidate_value
        ? "unavailable"
        : field.candidate_value === currentValue
          ? "unchanged"
          : currentValue ? "conflict" : "available";
      return { ...field, current_value: currentValue, state };
    }),
  };
}


function ReaderWorkspace({ snapshot }: { snapshot: ReaderSnapshot }) {
  const [editor, setEditor] = useState(() => createReaderEditorState(snapshot));
  const [enrichment, setEnrichment] = useState<EnrichmentState>({
    status: "idle",
    preview: null,
    selectedFields: [],
    message: "",
  });
  const tagBook = useApiResource(
    "reader-canonical-tag-book",
    () => apiClient.getTags({ limit: 100 }),
  );
  const metadataChanged = useMemo(
    () => changedMetadataFields(editor.metadata.draft, editor.metadata.baseline),
    [editor.metadata.draft, editor.metadata.baseline],
  );
  const hasDirtyDraft = shouldWarnBeforeReplacement(
    editor.metadata.draft,
    editor.metadata.baseline,
    editor.note.draft,
    editor.note.baseline,
  ) || Boolean(editor.tags.draft.trim());

  useEffect(() => {
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasDirtyDraft) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const warnBeforeLink = (event: MouseEvent) => {
      if (!hasDirtyDraft || event.defaultPrevented || event.button !== 0) return;
      const target = event.target;
      const link = target instanceof Element ? target.closest("a[href]") : null;
      if (!link) return;
      const destination = new URL(link.getAttribute("href") || "", window.location.href);
      if (destination.href === window.location.href) return;
      if (!window.confirm("Discard unsaved Reader changes and leave this paper?")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    document.addEventListener("click", warnBeforeLink, true);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      document.removeEventListener("click", warnBeforeLink, true);
    };
  }, [hasDirtyDraft]);

  const saveMetadata = async () => {
    if (!metadataChanged.length || editor.metadata.status === "saving" || editor.note.status === "saving" || enrichment.status === "saving") return;
    const changes = Object.fromEntries(
      metadataChanged.map((field) => [field, editor.metadata.draft[field]]),
    ) as Partial<EditablePaperMetadata>;
    setEditor((current) => ({
      ...current,
      metadata: { ...current.metadata, status: "saving", message: "Saving metadata…" },
    }));
    try {
      const response = await apiClient.saveReaderMetadata(
        snapshot.paper.paper_id,
        changes,
        editor.metadata.revision,
      );
      setEditor((current) => applyMetadataCommandResult(current, response));
    } catch (error) {
      const failure = errorState(error);
      setEditor((current) => ({
        ...current,
        metadata: { ...current.metadata, ...failure },
      }));
    }
  };

  const fetchMetadataCandidates = async (preserveSelection = false) => {
    if (enrichment.status === "loading" || enrichment.status === "saving") return;
    setEnrichment((current) => ({
      ...current,
      status: "loading",
      message: "Fetching metadata candidates…",
    }));
    try {
      const preview = await apiClient.previewMetadataEnrichment(snapshot.paper.paper_id);
      setEnrichment((current) => {
        const selectable = new Set(
          preview.fields
            .filter((field) => field.candidate_value && field.state !== "unchanged")
            .map((field) => field.field),
        );
        const selectedFields = preserveSelection
          ? current.selectedFields.filter((field) => selectable.has(field))
          : [];
        return {
          status: "ready",
          preview,
          selectedFields,
          message: preview.candidate_sources.length
            ? "Candidates are ready for review. Nothing has been saved."
            : "No candidate values were available. Nothing has been saved.",
        };
      });
    } catch (error) {
      const failure = enrichmentStateForError(error, "fetch");
      setEnrichment((current) => ({ ...current, ...failure }));
    }
  };

  const toggleCandidateField = (field: keyof EditablePaperMetadata) => {
    setEnrichment((current) => ({
      ...current,
      selectedFields: current.selectedFields.includes(field)
        ? current.selectedFields.filter((item) => item !== field)
        : [...current.selectedFields, field],
      message: "",
    }));
  };

  const applySelectedCandidates = async () => {
    if (!enrichment.preview || !enrichment.selectedFields.length || enrichment.status === "saving") return;
    const fieldsByName = new Map(enrichment.preview.fields.map((field) => [field.field, field]));
    const selectedFields = enrichment.selectedFields.filter((field) => {
      const candidate = fieldsByName.get(field);
      return Boolean(candidate?.candidate_value && candidate.state !== "unchanged");
    });
    if (!selectedFields.length) return;
    const changes = Object.fromEntries(selectedFields.map((field) => [
      field,
      fieldsByName.get(field)?.candidate_value ?? "",
    ])) as Partial<EditablePaperMetadata>;
    setEnrichment((current) => ({ ...current, status: "saving", message: "Applying selected metadata fields…" }));
    try {
      const response = await apiClient.saveReaderMetadata(
        snapshot.paper.paper_id,
        changes,
        enrichment.preview.metadata_revision,
      );
      setEditor((current) => applyMetadataEnrichmentCommandResult(current, response, selectedFields));
      setEnrichment((current) => {
        if (!current.preview) return current;
        const preview = refreshedCandidatePreview(current.preview, response.metadata, response.metadata_revision);
        return {
          status: "saved",
          preview,
          selectedFields: current.selectedFields.filter((field) => {
            const candidate = preview.fields.find((item) => item.field === field);
            return Boolean(candidate?.candidate_value && candidate.state !== "unchanged");
          }),
          message: response.status === "no_op"
            ? "Selected fields already matched the saved metadata."
            : `Saved selected fields: ${response.changed_fields.join(", ") || "none"}.`,
        };
      });
    } catch (error) {
      const failure = enrichmentStateForError(error, "apply");
      setEnrichment((current) => ({ ...current, ...failure }));
    }
  };

  const saveNote = async () => {
    if (editor.note.draft === editor.note.baseline || editor.note.status === "saving" || editor.metadata.status === "saving" || enrichment.status === "saving") return;
    setEditor((current) => ({
      ...current,
      note: { ...current.note, status: "saving", message: "Saving Reading Note…" },
    }));
    try {
      const response = await apiClient.saveReadingNote(
        snapshot.paper.paper_id,
        editor.note.draft,
        editor.note.sha256,
      );
      setEditor((current) => ({
        ...current,
        note: {
          ...current.note,
          draft: response.content,
          baseline: response.content,
          sha256: response.sha256,
          exists: true,
          status: "saved",
          message: response.status === "no_op" ? "Reading Note already matched the saved version." : "Reading Note saved.",
        },
      }));
    } catch (error) {
      const failure = errorState(error);
      setEditor((current) => ({
        ...current,
        note: { ...current.note, ...failure },
      }));
    }
  };

  const changePaperTag = async (operation: "add" | "remove", tag: string) => {
    const selectedTag = tag.trim();
    if (!selectedTag || editor.tags.status === "saving") return;
    setEditor((current) => ({
      ...current,
      tags: {
        ...current.tags,
        status: "saving",
        message: operation === "add" ? "Adding Paper tag…" : "Removing Paper tag…",
      },
    }));
    try {
      const response = operation === "add"
        ? await apiClient.addPaperTag(snapshot.paper.paper_id, selectedTag, editor.tags.revision)
        : await apiClient.removePaperTag(snapshot.paper.paper_id, selectedTag, editor.tags.revision);
      setEditor((current) => {
        const updated = applyPaperTagCommandResult(current, response);
        return {
          ...updated,
          tags: {
            ...updated.tags,
            draft: operation === "add" ? "" : current.tags.draft,
          },
        };
      });
    } catch (error) {
      const failure = errorState(error);
      setEditor((current) => ({
        ...current,
        tags: { ...current.tags, ...failure },
      }));
    }
  };

  const reloadMetadata = async () => {
    if (metadataChanged.length && !window.confirm("Replace this metadata draft with the current saved version?")) return;
    try {
      const current = await apiClient.getReaderSnapshot(snapshot.paper.paper_id);
      setEditor((state) => {
        const noteDirty = state.note.draft !== state.note.baseline;
        const refreshed = noteDirty
          ? refreshDirtyDraftHeader(state.note.draft, current.saved_note_content)
          : { content: current.saved_note_content, changed: false };
        return {
          ...state,
          metadata: {
            draft: { ...current.editable_metadata },
            baseline: { ...current.editable_metadata },
            revision: current.metadata_revision,
            status: "clean",
            message: "Current metadata loaded.",
          },
          note: {
            ...state.note,
            draft: refreshed.content,
            baseline: current.saved_note_content,
            sha256: current.saved_note_baseline.sha256,
            exists: current.saved_note_baseline.exists,
            status: refreshed.content === current.saved_note_content ? "clean" : "dirty",
            message: refreshed.changed
              ? "The current canonical header was applied; the unsaved note body was retained."
              : state.note.message,
          },
        };
      });
    } catch {
      setEditor((current) => ({
        ...current,
        metadata: { ...current.metadata, status: "error", message: "Current metadata could not be loaded. Your draft remains unchanged." },
      }));
    }
  };

  const reloadNote = async () => {
    if (
      editor.note.draft !== editor.note.baseline
      && !window.confirm("Replace this Reading Note draft with the current saved version?")
    ) return;
    try {
      const current = await apiClient.getReaderSnapshot(snapshot.paper.paper_id);
      setEditor((state) => ({
        ...state,
        note: {
          ...state.note,
          draft: current.saved_note_content,
          baseline: current.saved_note_content,
          sha256: current.saved_note_baseline.sha256,
          exists: current.saved_note_baseline.exists,
          status: "clean",
          message: "Current Reading Note loaded.",
        },
      }));
    } catch {
      setEditor((current) => ({
        ...current,
        note: { ...current.note, status: "error", message: "Current Reading Note could not be loaded. Your draft remains unchanged." },
      }));
    }
  };

  const reloadPaperTags = async () => {
    try {
      const current = await apiClient.getReaderSnapshot(snapshot.paper.paper_id);
      setEditor((state) => {
        const noteDirty = state.note.draft !== state.note.baseline;
        const refreshed = noteDirty && current.saved_note_content
          ? refreshDirtyDraftHeader(state.note.draft, current.saved_note_content)
          : { content: state.note.draft, changed: false };
        return {
          ...state,
          tags: {
            ...state.tags,
            values: [...current.paper.tags],
            revision: current.tags_revision,
            status: "clean",
            message: "Current Paper tags loaded. Your selected tag is still here.",
          },
          note: current.saved_note_available ? {
            ...state.note,
            draft: refreshed.content,
            baseline: current.saved_note_content,
            sha256: current.saved_note_baseline.sha256,
            exists: current.saved_note_baseline.exists,
            status: refreshed.content === current.saved_note_content ? "clean" : "dirty",
            message: refreshed.changed
              ? "The current canonical header was applied; the unsaved note body was retained."
              : state.note.message,
          } : state.note,
        };
      });
    } catch {
      setEditor((current) => ({
        ...current,
        tags: { ...current.tags, status: "error", message: "Current Paper tags could not be loaded. Your selected tag remains unchanged." },
      }));
    }
  };

  const noteUnavailable = snapshot.warnings.includes("saved_note_unavailable");
  const detailHref = `/papers/${encodeURIComponent(snapshot.paper.paper_id)}`;
  return (
    <>
      <Link className="back-link" href={detailHref}><ArrowLeft size={15} />Back to Paper Detail</Link>
      <PageHeader
        eyebrow="Reader"
        title={editor.metadata.draft.title || snapshot.paper.title}
        description={[
          editor.metadata.draft.authors || "Authors unknown",
          editor.metadata.draft.journal,
          editor.metadata.draft.year,
        ].filter(Boolean).join(" · ") || "Citation metadata is incomplete."}
        actions={<StatusBadge tone={snapshot.paper.archived ? "neutral" : "accent"}>{snapshot.paper.lifecycle_state}</StatusBadge>}
      />
      <div className="reader-layout">
        <section className="reader-stage" aria-label="Managed PDF viewing region">
          <ReaderPdf snapshot={snapshot} />
        </section>
        <aside className="reader-companion" aria-label="Reader editors">
          <section className="reader-editor" aria-labelledby="metadata-editor-title">
            <div className="reader-note__heading">
              <div>
                <p className="eyebrow">Bibliographic command</p>
                <h2 id="metadata-editor-title">Paper metadata</h2>
              </div>
              <StatusBadge tone={editor.metadata.status === "conflict" || editor.metadata.status === "error" ? "danger" : editor.metadata.status === "saved" ? "accent" : "neutral"}>
                {statusLabel(editor.metadata.status)}
              </StatusBadge>
            </div>
            <div className="reader-editor__fields">
              {(Object.keys(FIELD_LABELS) as Array<keyof EditablePaperMetadata>).map((field) => {
                const changed = metadataChanged.includes(field);
                const multiline = field === "abstract";
                return (
                  <label className={changed ? "reader-field reader-field--changed" : "reader-field"} key={field}>
                    <span>{FIELD_LABELS[field]}{changed ? " (changed)" : ""}</span>
                    {multiline ? (
                      <textarea
                        rows={5}
                        value={editor.metadata.draft[field]}
                        disabled={editor.metadata.status === "saving"}
                        onChange={(event) => setEditor((current) => {
                          const draft = { ...current.metadata.draft, [field]: event.target.value };
                          return {
                            ...current,
                            metadata: {
                              ...current.metadata,
                              draft,
                              status: changedMetadataFields(draft, current.metadata.baseline).length ? "dirty" : "clean",
                              message: "",
                            },
                          };
                        })}
                      />
                    ) : (
                      <input
                        type="text"
                        inputMode={field === "year" ? "numeric" : "text"}
                        value={editor.metadata.draft[field]}
                        disabled={editor.metadata.status === "saving"}
                        onChange={(event) => setEditor((current) => {
                          const draft = { ...current.metadata.draft, [field]: event.target.value };
                          return {
                            ...current,
                            metadata: {
                              ...current.metadata,
                              draft,
                              status: changedMetadataFields(draft, current.metadata.baseline).length ? "dirty" : "clean",
                              message: "",
                            },
                          };
                        })}
                      />
                    )}
                  </label>
                );
              })}
            </div>
            <p className="reader-editor__status" role="status" aria-live="polite">
              {editor.metadata.message || `${metadataChanged.length} changed field${metadataChanged.length === 1 ? "" : "s"}.`}
            </p>
            <div className="reader-editor__actions">
              <button className="reader-control" type="button" disabled={!metadataChanged.length || editor.metadata.status === "saving" || editor.note.status === "saving" || enrichment.status === "saving"} onClick={saveMetadata}>
                <Save size={15} />{editor.metadata.status === "saving" ? "Saving…" : "Save Metadata"}
              </button>
              {editor.metadata.status === "conflict" ? (
                <button className="reader-control reader-control--secondary" type="button" onClick={reloadMetadata}>
                  <RotateCcw size={15} />Reload current metadata
                </button>
              ) : null}
            </div>
          </section>

          <section className="reader-editor metadata-enrichment" aria-labelledby="metadata-enrichment-title">
            <div className="reader-note__heading">
              <div>
                <p className="eyebrow">Preview before save</p>
                <h2 id="metadata-enrichment-title">Metadata enrichment</h2>
              </div>
              <StatusBadge tone={enrichment.status === "conflict" || enrichment.status === "error" ? "danger" : enrichment.status === "saved" ? "accent" : "neutral"}>
                {enrichment.status === "ready" ? "Preview ready" : statusLabel(enrichment.status)}
              </StatusBadge>
            </div>
            <p className="reader-editor__status" role="status" aria-live="polite">
              {enrichment.message || "Fetch candidates from available DOI/Crossref, arXiv, and PDF-derived sources. This never saves metadata."}
            </p>
            {metadataChanged.length ? (
              <p className="metadata-enrichment__notice">
                The manual metadata editor has unsaved changes. Enrichment compares saved values and preserves every unselected manual draft field.
              </p>
            ) : null}
            {enrichment.preview ? (
              <>
                <p className="metadata-enrichment__sources">
                  Sources: {enrichment.preview.candidate_sources.length ? enrichment.preview.candidate_sources.join(", ") : "No candidate source supplied a supported field."}
                </p>
                <div className="metadata-enrichment__table" role="region" aria-label="Metadata candidate comparison">
                  <div className="metadata-enrichment__row metadata-enrichment__row--heading" aria-hidden="true">
                    <span>Apply</span><span>Field</span><span>Current saved value</span><span>Candidate value</span><span>Source / comparison</span>
                  </div>
                  {enrichment.preview.fields.map((field) => {
                    const selectable = Boolean(field.candidate_value) && field.state !== "unchanged";
                    const selected = enrichment.selectedFields.includes(field.field);
                    return (
                      <div className={`metadata-enrichment__row metadata-enrichment__row--${field.state}`} key={field.field}>
                        <label className="metadata-enrichment__select">
                          <input
                            type="checkbox"
                            checked={selected}
                            disabled={!selectable || enrichment.status === "saving"}
                            onChange={() => toggleCandidateField(field.field)}
                            aria-label={`Select ${FIELD_LABELS[field.field]} candidate`}
                          />
                        </label>
                        <strong>{FIELD_LABELS[field.field]}</strong>
                        <span className="metadata-enrichment__value">{field.current_value || "—"}</span>
                        <span className="metadata-enrichment__value">{field.candidate_value || "Unavailable"}</span>
                        <span className="metadata-enrichment__comparison">{field.source || "No source"}<br />{CANDIDATE_STATE_LABELS[field.state]}</span>
                      </div>
                    );
                  })}
                </div>
                {enrichment.preview.diagnostics.length ? (
                  <ul className="metadata-enrichment__diagnostics">
                    {enrichment.preview.diagnostics.map((diagnostic) => <li key={diagnostic}>{diagnostic}</li>)}
                  </ul>
                ) : null}
              </>
            ) : null}
            <div className="reader-editor__actions">
              <button className="reader-control" type="button" disabled={enrichment.status === "loading" || enrichment.status === "saving"} onClick={() => fetchMetadataCandidates(enrichment.status === "conflict")}>
                <RotateCcw size={15} />{enrichment.status === "loading" ? "Fetching…" : enrichment.preview ? "Fetch fresh candidates" : "Fetch candidates"}
              </button>
              <button className="reader-control" type="button" disabled={!enrichment.selectedFields.length || enrichment.status === "loading" || enrichment.status === "saving" || editor.metadata.status === "saving"} onClick={applySelectedCandidates}>
                <Save size={15} />{enrichment.status === "saving" ? "Applying…" : "Apply selected fields"}
              </button>
              {enrichment.status === "conflict" ? (
                <button className="reader-control reader-control--secondary" type="button" onClick={() => fetchMetadataCandidates(true)}>
                  <RotateCcw size={15} />Reload candidates and retry
                </button>
              ) : null}
            </div>
          </section>

          <section className="reader-editor" aria-labelledby="paper-tags-editor-title">
            <div className="reader-note__heading">
              <div>
                <p className="eyebrow">Independent tag command</p>
                <h2 id="paper-tags-editor-title">Paper tags</h2>
              </div>
              <StatusBadge tone={editor.tags.status === "conflict" || editor.tags.status === "error" ? "danger" : editor.tags.status === "saved" ? "accent" : "neutral"}>
                {statusLabel(editor.tags.status)}
              </StatusBadge>
            </div>
            <div className="tag-list" aria-label="Current Paper tags">
              {editor.tags.values.length ? editor.tags.values.map((tag) => (
                <button
                  className="reader-control reader-control--secondary"
                  type="button"
                  key={tag}
                  disabled={editor.tags.status === "saving"}
                  onClick={() => changePaperTag("remove", tag)}
                  aria-label={`Remove ${tag}`}
                >
                  Remove {tag}
                </button>
              )) : <span className="muted-text">No Paper tags are stored.</span>}
            </div>
            <label className="reader-field">
              <span>Add one tag</span>
              <input
                type="text"
                list="reader-canonical-tag-options"
                value={editor.tags.draft}
                disabled={editor.tags.status === "saving"}
                onChange={(event) => setEditor((current) => ({
                  ...current,
                  tags: {
                    ...current.tags,
                    draft: event.target.value,
                    status: event.target.value.trim() ? "dirty" : "clean",
                    message: "",
                  },
                }))}
              />
              <datalist id="reader-canonical-tag-options">
                {tagBook.status === "success" ? tagBook.data.items.map((tag) => (
                  <option key={tag.canonical_key} value={tag.canonical_key}>{tag.label}</option>
                )) : null}
              </datalist>
            </label>
            <p className="reader-editor__status" role="status" aria-live="polite">
              {editor.tags.message || (tagBook.status === "success" ? "Choose a canonical Tag Book value or enter one explicit compatible tag." : "Enter one explicit tag. Canonical Tag Book choices load when available.")}
            </p>
            <div className="reader-editor__actions">
              <button className="reader-control" type="button" disabled={!editor.tags.draft.trim() || editor.tags.status === "saving"} onClick={() => changePaperTag("add", editor.tags.draft)}>
                <Save size={15} />{editor.tags.status === "saving" ? "Saving…" : "Add Tag"}
              </button>
              {editor.tags.status === "conflict" ? (
                <button className="reader-control reader-control--secondary" type="button" onClick={reloadPaperTags}>
                  <RotateCcw size={15} />Reload current tags
                </button>
              ) : null}
            </div>
          </section>

          <section className="reader-editor reader-note" aria-labelledby="reading-note-editor-title">
            <div className="reader-note__heading">
              <div>
                <p className="eyebrow">Independent note command</p>
                <h2 id="reading-note-editor-title">Reading Note</h2>
              </div>
              <StatusBadge tone={editor.note.status === "conflict" || editor.note.status === "error" || noteUnavailable ? "danger" : editor.note.status === "saved" ? "accent" : "neutral"}>
                {noteUnavailable ? "Unavailable" : statusLabel(editor.note.status)}
              </StatusBadge>
            </div>
            {noteUnavailable ? (
              <div className="reader-note__message" role="status">
                The persisted note could not be read. Saving is disabled until the current version can be loaded.
              </div>
            ) : null}
            <label className="reader-field">
              <span>Complete Reading Note</span>
              <textarea
                className="reader-note__textarea"
                rows={24}
                value={editor.note.draft}
                disabled={editor.note.status === "saving" || noteUnavailable}
                onChange={(event) => setEditor((current) => ({
                  ...current,
                  note: {
                    ...current.note,
                    draft: event.target.value,
                    status: event.target.value === current.note.baseline ? "clean" : "dirty",
                    message: "",
                  },
                }))}
              />
            </label>
            <p className="reader-editor__status" role="status" aria-live="polite">
              {editor.note.message || (editor.note.exists ? "Editing the persisted Reading Note." : "No persisted note exists; Save will create it.")}
            </p>
            <div className="reader-editor__actions">
              <button className="reader-control" type="button" disabled={editor.note.draft === editor.note.baseline || editor.note.status === "saving" || editor.metadata.status === "saving" || enrichment.status === "saving" || noteUnavailable} onClick={saveNote}>
                <Save size={15} />{editor.note.status === "saving" ? "Saving…" : "Save Reading Note"}
              </button>
              {editor.note.status === "conflict" ? (
                <button className="reader-control reader-control--secondary" type="button" onClick={reloadNote}>
                  <RotateCcw size={15} />Reload current Reading Note
                </button>
              ) : null}
            </div>
          </section>
          <NoteBlocksWorkspace key={snapshot.paper.paper_id} paperId={snapshot.paper.paper_id} />
        </aside>
      </div>
    </>
  );
}


export function ReaderView({ paperId }: { paperId: string }) {
  const [retryCount, setRetryCount] = useState(0);
  const resource = useApiResource(
    `reader-snapshot:${paperId}:${retryCount}`,
    () => apiClient.getReaderSnapshot(paperId),
  );
  return (
    <div className="page-stack">
      {resource.status === "loading" ? <LoadingState label="Loading Reader snapshot" /> : null}
      {resource.status === "unavailable" ? (
        <div className="reader-metadata-state">
          <UnavailableState description={resource.message} />
          <button className="reader-control" type="button" onClick={() => setRetryCount((value) => value + 1)}>Retry local API</button>
        </div>
      ) : null}
      {resource.status === "not-found" ? <EmptyState title="Paper not found" description="The requested paper identity is not present in the local read model." /> : null}
      {resource.status === "error" ? (
        <div className="reader-metadata-state">
          <ErrorState description={resource.message} />
          <button className="reader-control" type="button" onClick={() => setRetryCount((value) => value + 1)}>Retry local API</button>
        </div>
      ) : null}
      {resource.status === "success" ? (
        <ReaderWorkspace key={resource.data.paper.paper_id} snapshot={resource.data} />
      ) : null}
    </div>
  );
}
