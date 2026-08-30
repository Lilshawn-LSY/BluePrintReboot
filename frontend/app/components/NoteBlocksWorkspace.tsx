"use client";

import { Edit3, Link2, Plus, RotateCcw, Save, Unlink, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ApiClientError, apiClient } from "../lib/api/client";
import type {
  EditableNoteBlockContent,
  NoteBlock,
  NoteBlockCollection,
  NoteBlockProjectLink,
  NoteBlockType,
  ProjectListItem,
  ProjectLinkType,
} from "../lib/api/types";
import {
  changedNoteBlockFields,
  createNoteBlockEditorState,
  editableNoteBlock,
} from "../lib/note-blocks/editor-state.mjs";
import type { NoteBlockEditorState } from "../lib/note-blocks/editor-state.mjs";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "./AsyncStates";
import { StatusBadge } from "./StatusBadge";
import { RelationshipLabel } from "./RelationshipLabel";
import { SaveStatus } from "./SaveStatus";
import {
  applyLatestRevisionDraft,
  beginRevisionSave,
  clearPersistentRevisionDraft,
  completeRevisionSave,
  draftStorageKey,
  editRevisionDraft,
  failRevisionSave,
  keepMyRevisionDraft,
  persistRevisionDraft,
  readPersistentRevisionDraft,
  receiveRemoteRevision,
} from "../lib/drafts/revision-draft.mjs";


const BLOCK_TYPES: NoteBlockType[] = [
  "summary",
  "claim",
  "method",
  "evidence",
  "question",
  "idea",
  "limitation",
];

const LINK_TYPES: ProjectLinkType[] = [
  "related",
  "background",
  "key_reference",
  "supports_project",
  "raises_question",
  "idea_for_project",
];

type CollectionState =
  | { status: "loading" }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; data: NoteBlockCollection };

type ProjectPickerState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ProjectListItem[] };

type LinkStatus = "idle" | "saving" | "conflict" | "error";


function linkFailure(error: unknown): { status: LinkStatus; message: string } {
  if (error instanceof ApiClientError && error.kind === "conflict") {
    return {
      status: "conflict",
      message: "The Project link collection changed. Your Project and link-type selection is preserved.",
    };
  }
  return {
    status: "error",
    message: error instanceof ApiClientError
      ? `${error.message} Your Project and link-type selection is preserved.`
      : "The Project link command failed. Your selection is preserved.",
  };
}

function replaceBlock(
  collection: NoteBlockCollection,
  block: NoteBlock,
  revision: string,
  total: number,
): NoteBlockCollection {
  const exists = collection.items.some((item) => item.id === block.id);
  return {
    ...collection,
    items: exists
      ? collection.items.map((item) => item.id === block.id ? block : item)
      : [block, ...collection.items],
    note_blocks_revision: revision,
    total,
  };
}

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}


export function NoteBlocksWorkspace({ paperId, focusBlockId = "" }: { paperId: string; focusBlockId?: string }) {
  const [collection, setCollection] = useState<CollectionState>({ status: "loading" });
  const [editor, setEditor] = useState<NoteBlockEditorState | null>(null);
  const [expandedBlockId, setExpandedBlockId] = useState("");
  const [tagDraft, setTagDraft] = useState("");
  const [projects, setProjects] = useState<ProjectPickerState>({ status: "loading" });
  const [linkingBlockId, setLinkingBlockId] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedLinkType, setSelectedLinkType] = useState<ProjectLinkType>("related");
  const [linkStatus, setLinkStatus] = useState<LinkStatus>("idle");
  const [linkMessage, setLinkMessage] = useState("");
  const focusedDeepLinkRef = useRef("");
  const editorTitleRef = useRef<HTMLInputElement | null>(null);
  const editorDraftKey = draftStorageKey("note-block", `${paperId}:${editor?.blockId || "new"}`);
  const changedFields = useMemo(
    () => editor ? changedNoteBlockFields(editor.draft, editor.baseline) : [],
    [editor],
  );
  const dirty = changedFields.length > 0;

  useEffect(() => {
    if (editor) persistRevisionDraft(browserStorage(), editorDraftKey, editor);
  }, [editor, editorDraftKey]);

  function updateEditor(update: (state: NoteBlockEditorState) => NoteBlockEditorState) {
    setEditor((current) => {
      if (!current) return current;
      const next = update(current);
      persistRevisionDraft(browserStorage(), editorDraftKey, next);
      return next;
    });
  }

  async function loadCollection(options: { preserveDraft?: boolean } = {}) {
    try {
      const current = await apiClient.getNoteBlocks(paperId);
      setCollection({ status: "ready", data: current });
      if (options.preserveDraft) {
        setEditor((state) => {
          if (!state || state.mode !== "edit") return state;
          const persisted = current.items.find((block) => block.id === state.blockId);
          if (!persisted) return state;
          const received = receiveRemoteRevision(state, {
            value: editableNoteBlock(persisted),
            revision: current.note_blocks_revision,
            changedElsewhere: current.note_blocks_revision !== state.revision
              && changedNoteBlockFields(state.draft, state.baseline).length > 0,
          });
          const next = {
            ...received,
            status: received.saveState === "saved" ? "clean" as const : "conflict" as const,
            message: received.saveState === "saved"
              ? "Current collection loaded."
              : "The latest saved Note Block was loaded separately. Choose which version to keep.",
          };
          persistRevisionDraft(browserStorage(), editorDraftKey, next);
          return next;
        });
      }
      return current;
    } catch (error) {
      const unavailable = error instanceof ApiClientError
        && (error.kind === "unavailable" || error.kind === "read-model");
      setCollection({
        status: unavailable ? "unavailable" : "error",
        message: error instanceof ApiClientError
          ? error.message
          : "Structured Note Blocks could not be loaded.",
      });
      return null;
    }
  }

  useEffect(() => {
    let active = true;
    apiClient.getNoteBlocks(paperId)
      .then((data) => {
        if (active) setCollection({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const unavailable = error instanceof ApiClientError
          && (error.kind === "unavailable" || error.kind === "read-model");
        setCollection({
          status: unavailable ? "unavailable" : "error",
          message: error instanceof ApiClientError
            ? error.message
            : "Structured Note Blocks could not be loaded.",
        });
      });
    apiClient.getAllProjects()
      .then((data) => {
        if (!active) return;
        setProjects({ status: "ready", data });
        const firstWritable = data.find((project) => project.status !== "archived");
        setSelectedProjectId((current) => current || firstWritable?.project_id || "");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setProjects({
          status: "error",
          message: error instanceof ApiClientError ? error.message : "The Project picker could not be loaded.",
        });
      });
    return () => { active = false; };
  }, [paperId]);

  useEffect(() => {
    if (!focusBlockId) {
      focusedDeepLinkRef.current = "";
      return;
    }
    if (collection.status !== "ready" || focusedDeepLinkRef.current === focusBlockId) return;
    const target = document.getElementById(`note-block-${focusBlockId}`);
    if (!target) return;
    setExpandedBlockId(focusBlockId);
    focusedDeepLinkRef.current = focusBlockId;
    const frame = window.requestAnimationFrame(() => {
      target.scrollIntoView({ block: "center" });
      target.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [collection, focusBlockId]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const beforeNavigation = (event: MouseEvent) => {
      if (!dirty || event.defaultPrevented || event.button !== 0) return;
      const anchor = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!anchor || window.confirm("Leave this Paper? Your locally preserved Note Block draft will remain available.")) return;
      event.preventDefault();
      event.stopPropagation();
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", beforeNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", beforeNavigation, true);
    };
  }, [dirty]);

  function beginCreate() {
    if (dirty && !window.confirm("Switch editors? Your current locally preserved Note Block draft will remain available.")) return;
    const next = createNoteBlockEditorState(
      null,
      readPersistentRevisionDraft(browserStorage(), draftStorageKey("note-block", `${paperId}:new`)),
      collection.status === "ready" ? collection.data.note_blocks_revision : "",
    );
    setEditor(next);
    setExpandedBlockId("");
    setTagDraft(next.draft.tags.join(", "));
  }

  function beginEdit(block: NoteBlock) {
    if (dirty && !window.confirm("Switch editors? Your current locally preserved Note Block draft will remain available.")) return;
    const next = createNoteBlockEditorState(
      block,
      readPersistentRevisionDraft(browserStorage(), draftStorageKey("note-block", `${paperId}:${block.id}`)),
      collection.status === "ready" ? collection.data.note_blocks_revision : "",
    );
    setEditor(next);
    setExpandedBlockId(block.id);
    setTagDraft(next.draft.tags.join(", "));
  }

  function updateDraft(field: keyof EditableNoteBlockContent, value: string | string[]) {
    updateEditor((current) => {
      const draft = { ...current.draft, [field]: value } as EditableNoteBlockContent;
      const updated = editRevisionDraft(current, draft);
      return {
        ...updated,
        status: changedNoteBlockFields(draft, current.baseline).length ? "dirty" : "clean",
        message: "",
      };
    });
  }

  async function saveBlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor || collection.status !== "ready") return;
    const activeEditor = editor;
    const started = beginRevisionSave(activeEditor);
    if (!started.request) return;
    const request = started.request;
    updateEditor(() => ({ ...started.state, status: "saving", message: "Saving Note Block…" }));
    try {
      const response = activeEditor.mode === "create"
        ? await apiClient.createNoteBlock(
            paperId,
            request.draft,
            request.revision,
          )
        : await apiClient.updateNoteBlock(
            paperId,
            activeEditor.blockId,
            (changedNoteBlockFields(request.draft, activeEditor.baseline).length
              ? Object.fromEntries(
                  changedNoteBlockFields(request.draft, activeEditor.baseline).map((field) => [field, request.draft[field]]),
                )
              : { text: request.draft.text }
            ) as Partial<EditableNoteBlockContent>,
            request.revision,
          );
      setCollection((current) => current.status === "ready"
        ? { status: "ready", data: replaceBlock(current.data, response.block, response.note_blocks_revision, response.total) }
        : current);
      updateEditor((current) => {
        const saved = completeRevisionSave(current, request.token, {
          value: editableNoteBlock(response.block),
          revision: response.note_blocks_revision,
        });
        const next = {
          ...saved,
          mode: "edit" as const,
          blockId: response.block.id,
          status: saved.saveState === "saved" ? response.status === "no_op" ? "no_op" as const : "saved" as const : "dirty" as const,
          message: saved.saveState === "saved"
            ? response.status === "no_op" ? "The Note Block already matched the saved version." : "Note Block saved."
            : "The saved Note Block is current. Newer local edits are still unsaved.",
        };
        if (saved.saveState === "saved") setTagDraft(response.block.tags.join(", "));
        return next;
      });
      if (activeEditor.mode === "create") {
        clearPersistentRevisionDraft(browserStorage(), draftStorageKey("note-block", `${paperId}:new`));
        setExpandedBlockId(response.block.id);
        window.requestAnimationFrame(() => editorTitleRef.current?.focus());
      }
    } catch (error) {
      let remote: { block: NoteBlock; revision: string } | null = null;
      if (error instanceof ApiClientError && error.kind === "conflict") {
        try {
          const latest = await apiClient.getNoteBlocks(paperId);
          const block = latest.items.find((item) => item.id === activeEditor.blockId);
          remote = block ? { block, revision: latest.note_blocks_revision } : null;
        } catch { /* retain the local draft until the collection is reachable */ }
      }
      updateEditor((current) => {
        let failed = failRevisionSave(current, request.token, error instanceof ApiClientError ? error.kind : "error");
        if (remote) failed = receiveRemoteRevision(failed, {
          value: editableNoteBlock(remote.block),
          revision: remote.revision,
          changedElsewhere: true,
        });
        return {
          ...failed,
          status: failed.saveState === "changed_elsewhere" ? "conflict" : "error",
          message: failed.saveState === "changed_elsewhere"
            ? "This Note Block changed elsewhere. Your draft and the latest saved block are both preserved."
            : failed.saveState === "offline"
              ? "The local API is unavailable. Your Note Block draft is preserved locally."
              : "Save failed. Your Note Block draft remains preserved locally.",
        };
      });
    }
  }

  async function addProjectLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!linkingBlockId || !selectedProjectId) return;
    setLinkStatus("saving");
    setLinkMessage("Linking Note Block to Project…");
    try {
      const project = await apiClient.getCompleteProject(selectedProjectId);
      if (project.status === "archived") {
        throw new ApiClientError("Archived Projects do not allow new links.", "conflict", 409);
      }
      const response = await apiClient.addProjectNoteBlockLink(
        selectedProjectId,
        paperId,
        linkingBlockId,
        selectedLinkType,
        project.links_revision,
      );
      setCollection((current) => {
        if (current.status !== "ready") return current;
        const existing = current.data.project_links.some((link) => link.link_id === response.link.link_id);
        const nextLink: NoteBlockProjectLink = {
          link_id: response.link.link_id,
          project_id: response.link.project_id,
          project_name: project.name,
          project_status: response.project.status,
          note_block_id: response.link.note_block_id,
          link_type: response.link.link_type,
          links_revision: response.project.links_revision,
        };
        return {
          status: "ready",
          data: {
            ...current.data,
            project_links: (existing
              ? current.data.project_links
              : [...current.data.project_links, nextLink]
            ).map((link) => link.project_id === response.project.project_id
              ? { ...link, links_revision: response.project.links_revision }
              : link),
          },
        };
      });
      setLinkStatus("idle");
      setLinkMessage(response.status === "unchanged"
        ? "That exact Note Block link already exists; nothing was written."
        : "Note Block linked to Project.");
    } catch (error) {
      const failure = linkFailure(error);
      setLinkStatus(failure.status);
      setLinkMessage(failure.message);
    }
  }

  async function removeProjectLink(link: NoteBlockProjectLink) {
    if (!window.confirm(`Remove this Note Block link from “${link.project_name || link.project_id}”? The Note Block and Paper will remain.`)) return;
    setLinkStatus("saving");
    setLinkMessage("Removing Note Block link…");
    try {
      const response = await apiClient.removeProjectNoteBlockLink(
        link.project_id,
        link.link_id,
        link.links_revision,
      );
      setCollection((current) => current.status === "ready" ? {
        status: "ready",
        data: {
          ...current.data,
          project_links: current.data.project_links
            .filter((item) => item.link_id !== response.link.link_id)
            .map((item) => item.project_id === response.project.project_id
              ? { ...item, links_revision: response.project.links_revision }
              : item),
        },
      } : current);
      setLinkStatus("idle");
      setLinkMessage("Project link removed. The Note Block and Paper were not changed.");
    } catch (error) {
      const failure = linkFailure(error);
      setLinkStatus(failure.status);
      setLinkMessage(failure.message);
    }
  }

  if (collection.status === "loading") return <LoadingState label="Loading structured Note Blocks" />;
  if (collection.status === "unavailable") {
    return <UnavailableState description={collection.message} onRetry={() => { setCollection({ status: "loading" }); void loadCollection({ preserveDraft: true }); }} />;
  }
  if (collection.status === "error") {
    return <ErrorState title="Note Blocks unavailable" description={collection.message} onRetry={() => { setCollection({ status: "loading" }); void loadCollection({ preserveDraft: true }); }} />;
  }

  const writableProjects = projects.status === "ready"
    ? projects.data.filter((project) => project.status !== "archived")
    : [];

  return (
    <section className="reader-editor reader-note-blocks" aria-labelledby="note-block-editor-title">
      <div className="reader-note__heading">
        <div>
          <h2 id="note-block-editor-title">Note Blocks</h2>
        </div>
        <StatusBadge tone={editor?.status === "conflict" || editor?.status === "error" ? "danger" : "neutral"}>
          {collection.data.total} blocks
        </StatusBadge>
      </div>
      <div className="reader-editor__actions">
        <button className="reader-control" type="button" onClick={beginCreate} disabled={Boolean(editor?.activeSave)}><Plus size={15} />Add</button>
        <button
          className="reader-control reader-control--secondary"
          type="button"
          onClick={() => { setCollection({ status: "loading" }); void loadCollection({ preserveDraft: true }); }}
        ><RotateCcw size={15} />Reload collection</button>
      </div>
      {collection.data.project_links_state === "unavailable" ? (
        <p className="reader-editor__status">Project-link summaries are temporarily unavailable; Note Block editing remains available.</p>
      ) : null}
      {collection.data.items.length === 0 ? (
        <EmptyState title="No structured Note Blocks" description="Create the first block explicitly; nothing is autosaved." />
      ) : (
        <div className="note-block-list">
          {collection.data.items.map((block) => {
            const links = collection.data.project_links.filter((link) => link.note_block_id === block.id);
            return (
              <article className={expandedBlockId === block.id ? "note-block-card is-expanded" : "note-block-card"} id={`note-block-${block.id}`} key={block.id} tabIndex={focusBlockId === block.id ? -1 : undefined}>
                <div className="reader-note__heading">
                  <div><strong>{block.title || block.block_type}</strong></div>
                  <StatusBadge>{block.block_type}</StatusBadge>
                </div>
                {block.text ? <p>{block.text}</p> : <p className="muted-text">No block text.</p>}
                <p className="muted-text">{[block.page && `Page ${block.page}`, block.figure && `Figure ${block.figure}`, block.tags.join(", ")].filter(Boolean).join(" · ")}</p>
                {expandedBlockId === block.id && links.length ? (
                  <div className="tag-list">
                    {links.map((link) => (
                      <span className="note-block-project-link" key={link.link_id}>
                        <span className="note-block-project-link__summary"><span>{link.project_name || link.project_id}</span><RelationshipLabel type={link.link_type} /></span>
                        {link.project_status !== "archived" && link.project_status !== "unavailable" ? (
                          <button className="reader-control reader-control--secondary" type="button" disabled={linkStatus === "saving"} onClick={() => removeProjectLink(link)}><Unlink size={14} />Unlink</button>
                        ) : null}
                      </span>
                    ))}
                  </div>
                ) : expandedBlockId === block.id ? <p className="muted-text">Not linked to a Project.</p> : null}
                <div className="reader-editor__actions">
                  <button className="reader-control reader-control--secondary" type="button" onClick={() => beginEdit(block)} disabled={Boolean(editor?.activeSave)}><Edit3 size={15} />Edit</button>
                  <button className="reader-control reader-control--secondary" type="button" onClick={() => { setExpandedBlockId((current) => current === block.id ? "" : block.id); setLinkingBlockId((current) => current === block.id ? "" : current); }}>{expandedBlockId === block.id ? "Collapse" : "Details"}</button>
                  {expandedBlockId === block.id ? <button className="reader-control reader-control--secondary" type="button" onClick={() => setLinkingBlockId((current) => current === block.id ? "" : block.id)}><Link2 size={15} />Link to Project</button> : null}
                </div>
                {linkingBlockId === block.id ? (
                  <form className="project-link-form project-link-form--note-block" onSubmit={addProjectLink}>
                    {projects.status === "loading" ? <span className="muted-text">Loading Projects…</span> : null}
                    {projects.status === "error" ? <span className="reader-editor__status">{projects.message}</span> : null}
                    {projects.status === "ready" && writableProjects.length === 0 ? <span className="muted-text">No writable Projects are available.</span> : null}
                    {writableProjects.length ? (
                      <>
                        <label className="reader-field"><span>Project</span><select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)}>{writableProjects.map((project) => <option key={project.project_id} value={project.project_id}>{project.name}</option>)}</select></label>
                        <label className="reader-field"><span>Link type</span><select value={selectedLinkType} onChange={(event) => setSelectedLinkType(event.target.value as ProjectLinkType)}>{LINK_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
                        <button className="reader-control" type="submit" disabled={!selectedProjectId || linkStatus === "saving"}><Link2 size={15} />Link</button>
                      </>
                    ) : null}
                  </form>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
      {linkMessage ? <p className="reader-editor__status" role="status">{linkMessage}</p> : null}
      {linkStatus === "conflict" ? (
        <button className="reader-control reader-control--secondary" type="button" onClick={() => void loadCollection({ preserveDraft: true })}><RotateCcw size={15} />Reload links and keep draft</button>
      ) : null}
      {editor ? (
        <form className="note-block-form" onSubmit={saveBlock}>
          <div className="reader-note__heading">
            <h3>{editor.mode === "create" ? "Create Note Block" : "Edit Note Block"}</h3>
            <SaveStatus state={editor.saveState} />
          </div>
          <label className={`reader-field ${changedFields.includes("block_type") ? "reader-field--changed" : ""}`}><span>Block type{changedFields.includes("block_type") ? " (changed)" : ""}</span><select value={editor.draft.block_type} onChange={(event) => updateDraft("block_type", event.target.value as NoteBlockType)}>{BLOCK_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
          <label className={`reader-field ${changedFields.includes("title") ? "reader-field--changed" : ""}`}><span>Title{changedFields.includes("title") ? " (changed)" : ""}</span><input ref={editorTitleRef} maxLength={1000} value={editor.draft.title} onChange={(event) => updateDraft("title", event.target.value)} /></label>
          <label className={`reader-field ${changedFields.includes("text") ? "reader-field--changed" : ""}`}><span>Text{changedFields.includes("text") ? " (changed)" : ""}</span><textarea rows={8} maxLength={100000} value={editor.draft.text} onChange={(event) => updateDraft("text", event.target.value)} /></label>
          <div className="project-form-grid">
            <label className={`reader-field ${changedFields.includes("page") ? "reader-field--changed" : ""}`}><span>Page</span><input maxLength={100} value={editor.draft.page} onChange={(event) => updateDraft("page", event.target.value)} /></label>
            <label className={`reader-field ${changedFields.includes("figure") ? "reader-field--changed" : ""}`}><span>Figure</span><input maxLength={500} value={editor.draft.figure} onChange={(event) => updateDraft("figure", event.target.value)} /></label>
          </div>
          <label className={`reader-field ${changedFields.includes("quote") ? "reader-field--changed" : ""}`}><span>Quote</span><textarea rows={4} maxLength={100000} value={editor.draft.quote} onChange={(event) => updateDraft("quote", event.target.value)} /></label>
          <label className={`reader-field ${changedFields.includes("tags") ? "reader-field--changed" : ""}`}><span>Tags (comma separated)</span><input value={tagDraft} onChange={(event) => { const value = event.target.value; setTagDraft(value); updateDraft("tags", value.split(",").map((tag) => tag.trim()).filter(Boolean)); }} /></label>
          <p className="reader-editor__status" role="status">{editor.message || `${changedFields.length} changed field${changedFields.length === 1 ? "" : "s"}.`}</p>
          <div className="reader-editor__actions">
            <button className="reader-control" type="submit" disabled={!dirty || Boolean(editor.activeSave) || editor.saveState === "changed_elsewhere"}><Save size={15} />{editor.saveState === "saving" ? "Saving…" : "Save Note Block"}</button>
            <button className="reader-control reader-control--secondary" type="button" disabled={Boolean(editor.activeSave)} onClick={() => { setEditor(null); setTagDraft(""); }}><X size={15} />Cancel (keep draft)</button>
            {editor.saveState === "changed_elsewhere" ? <>
              <button className="reader-control reader-control--secondary" type="button" disabled={editor.remoteRevision === editor.revision} onClick={() => updateEditor((current) => ({ ...keepMyRevisionDraft(current), status: "dirty", message: "Your local draft will be saved against the latest collection." }))}>Keep my draft</button>
              <button className="reader-control reader-control--secondary" type="button" onClick={() => {
                if (!window.confirm("Use the latest saved Note Block and discard the local draft?")) return;
                updateEditor((current) => ({ ...applyLatestRevisionDraft(current), status: "clean", message: "Latest saved Note Block in use." }));
              }}>Use latest saved version</button>
              <button className="reader-control reader-control--secondary" type="button" onClick={() => void loadCollection({ preserveDraft: true })}><RotateCcw size={15} />Reload current collection</button>
              <details className="reader-note__conflict-review"><summary>Review local and latest</summary><h3>My draft</h3><pre>{JSON.stringify(editor.draft, null, 2)}</pre><h3>Latest saved value</h3><pre>{JSON.stringify(editor.remote, null, 2)}</pre></details>
            </> : null}
          </div>
        </form>
      ) : null}
    </section>
  );
}
