"use client";

import { ArrowLeft, RotateCcw, Save } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { PdfJsReader } from "../components/PdfJsReader";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";
import type { EditablePaperMetadata, ReaderSnapshot } from "../lib/api/types";
import {
  applyMetadataCommandResult,
  changedMetadataFields,
  createReaderEditorState,
  refreshDirtyDraftHeader,
  shouldWarnBeforeReplacement,
} from "../lib/reader/editor-state.mjs";


type EditorStatus = "clean" | "dirty" | "saving" | "saved" | "conflict" | "error";

const FIELD_LABELS: Record<keyof EditablePaperMetadata, string> = {
  title: "Title",
  authors: "Authors",
  year: "Year",
  journal: "Journal",
  doi: "DOI",
  abstract: "Abstract",
  keywords: "Keywords",
};


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


function statusLabel(status: EditorStatus): string {
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


function ReaderWorkspace({ snapshot }: { snapshot: ReaderSnapshot }) {
  const [editor, setEditor] = useState(() => createReaderEditorState(snapshot));
  const metadataChanged = useMemo(
    () => changedMetadataFields(editor.metadata.draft, editor.metadata.baseline),
    [editor.metadata.draft, editor.metadata.baseline],
  );
  const hasDirtyDraft = shouldWarnBeforeReplacement(
    editor.metadata.draft,
    editor.metadata.baseline,
    editor.note.draft,
    editor.note.baseline,
  );

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
    if (!metadataChanged.length || editor.metadata.status === "saving" || editor.note.status === "saving") return;
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

  const saveNote = async () => {
    if (editor.note.draft === editor.note.baseline || editor.note.status === "saving" || editor.metadata.status === "saving") return;
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
              <button className="reader-control" type="button" disabled={!metadataChanged.length || editor.metadata.status === "saving" || editor.note.status === "saving"} onClick={saveMetadata}>
                <Save size={15} />{editor.metadata.status === "saving" ? "Saving…" : "Save Metadata"}
              </button>
              {editor.metadata.status === "conflict" ? (
                <button className="reader-control reader-control--secondary" type="button" onClick={reloadMetadata}>
                  <RotateCcw size={15} />Reload current metadata
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
              <button className="reader-control" type="button" disabled={editor.note.draft === editor.note.baseline || editor.note.status === "saving" || editor.metadata.status === "saving" || noteUnavailable} onClick={saveNote}>
                <Save size={15} />{editor.note.status === "saving" ? "Saving…" : "Save Reading Note"}
              </button>
              {editor.note.status === "conflict" ? (
                <button className="reader-control reader-control--secondary" type="button" onClick={reloadNote}>
                  <RotateCcw size={15} />Reload current Reading Note
                </button>
              ) : null}
            </div>
          </section>
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
