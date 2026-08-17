"use client";

import { Edit3, Link2, Plus, RotateCcw, Save, Unlink, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
  applyNoteBlockCommandResult,
  changedNoteBlockFields,
  createNoteBlockEditorState,
  preserveNoteBlockDraftAfterFailure,
} from "../lib/note-blocks/editor-state.mjs";
import type { NoteBlockEditorState } from "../lib/note-blocks/editor-state.mjs";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "./AsyncStates";
import { StatusBadge } from "./StatusBadge";


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


function statusLabel(status: NoteBlockEditorState["status"]): string {
  return status === "no_op" ? "No-op" : status.charAt(0).toUpperCase() + status.slice(1);
}

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
      : [...collection.items, block],
    note_blocks_revision: revision,
    total,
  };
}


export function NoteBlocksWorkspace({ paperId }: { paperId: string }) {
  const [collection, setCollection] = useState<CollectionState>({ status: "loading" });
  const [editor, setEditor] = useState<NoteBlockEditorState | null>(null);
  const [tagDraft, setTagDraft] = useState("");
  const [projects, setProjects] = useState<ProjectPickerState>({ status: "loading" });
  const [linkingBlockId, setLinkingBlockId] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedLinkType, setSelectedLinkType] = useState<ProjectLinkType>("related");
  const [linkStatus, setLinkStatus] = useState<LinkStatus>("idle");
  const [linkMessage, setLinkMessage] = useState("");
  const changedFields = useMemo(
    () => editor ? changedNoteBlockFields(editor.draft, editor.baseline) : [],
    [editor],
  );
  const dirty = changedFields.length > 0;

  async function loadCollection(options: { preserveDraft?: boolean } = {}) {
    try {
      const current = await apiClient.getNoteBlocks(paperId);
      setCollection({ status: "ready", data: current });
      if (options.preserveDraft && editor?.mode === "edit") {
        const persisted = current.items.find((block) => block.id === editor.blockId);
        if (persisted) {
          const fresh = createNoteBlockEditorState(persisted);
          setEditor((state) => state ? {
            ...state,
            baseline: fresh.baseline,
            status: changedNoteBlockFields(state.draft, fresh.baseline).length ? "dirty" : "clean",
            message: "Current collection loaded; your draft was preserved.",
          } : state);
        }
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
    if (collection.status !== "ready") return;
    const target = new URLSearchParams(window.location.search).get("noteBlock");
    if (!target) return;
    document.getElementById(`note-block-${target}`)?.scrollIntoView({ block: "center" });
  }, [collection]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const beforeNavigation = (event: MouseEvent) => {
      if (!dirty || event.defaultPrevented || event.button !== 0) return;
      const anchor = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!anchor || window.confirm("Discard the unsaved Note Block draft and leave this Paper?")) return;
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
    if (dirty && !window.confirm("Discard the current Note Block draft?")) return;
    const next = createNoteBlockEditorState();
    setEditor(next);
    setTagDraft("");
  }

  function beginEdit(block: NoteBlock) {
    if (dirty && !window.confirm("Discard the current Note Block draft?")) return;
    setEditor(createNoteBlockEditorState(block));
    setTagDraft(block.tags.join(", "));
  }

  function updateDraft(field: keyof EditableNoteBlockContent, value: string | string[]) {
    setEditor((current) => {
      if (!current) return current;
      const draft = { ...current.draft, [field]: value } as EditableNoteBlockContent;
      return {
        ...current,
        draft,
        status: changedNoteBlockFields(draft, current.baseline).length ? "dirty" : "clean",
        message: "",
      };
    });
  }

  async function saveBlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor || collection.status !== "ready" || editor.status === "saving") return;
    const activeEditor = editor;
    setEditor((current) => current ? { ...current, status: "saving", message: "Saving Note Block…" } : current);
    try {
      const response = activeEditor.mode === "create"
        ? await apiClient.createNoteBlock(
            paperId,
            activeEditor.draft,
            collection.data.note_blocks_revision,
          )
        : await apiClient.updateNoteBlock(
            paperId,
            activeEditor.blockId,
            (changedFields.length
              ? Object.fromEntries(
                  changedFields.map((field) => [field, activeEditor.draft[field]]),
                )
              : { text: activeEditor.draft.text }
            ) as Partial<EditableNoteBlockContent>,
            collection.data.note_blocks_revision,
          );
      setCollection((current) => current.status === "ready"
        ? { status: "ready", data: replaceBlock(current.data, response.block, response.note_blocks_revision, response.total) }
        : current);
      setEditor((current) => current ? applyNoteBlockCommandResult(current, response) : current);
      setTagDraft(response.block.tags.join(", "));
    } catch (error) {
      const kind = error instanceof ApiClientError ? error.kind : "error";
      setEditor((current) => current ? preserveNoteBlockDraftAfterFailure(current, kind) : current);
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
    <section className="reader-editor" aria-labelledby="note-block-editor-title">
      <div className="reader-note__heading">
        <div>
          <h2 id="note-block-editor-title">Structured Note Blocks</h2>
        </div>
        <StatusBadge tone={editor?.status === "conflict" || editor?.status === "error" ? "danger" : "neutral"}>
          {collection.data.total} blocks
        </StatusBadge>
      </div>
      <div className="reader-editor__actions">
        <button className="reader-control" type="button" onClick={beginCreate}><Plus size={15} />New Note Block</button>
        <button
          className="reader-control reader-control--secondary"
          type="button"
          onClick={() => {
            if (dirty && !window.confirm("Reload and discard the current Note Block draft?")) return;
            setEditor(null);
            setCollection({ status: "loading" });
            void loadCollection();
          }}
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
              <article className="note-block-card" id={`note-block-${block.id}`} key={block.id}>
                <div className="reader-note__heading">
                  <div><strong>{block.title || block.block_type}</strong><small className="mono-id">{block.id}</small></div>
                  <StatusBadge>{block.block_type}</StatusBadge>
                </div>
                {block.text ? <p>{block.text}</p> : <p className="muted-text">No block text.</p>}
                <p className="muted-text">{[block.page && `Page ${block.page}`, block.figure && `Figure ${block.figure}`, block.tags.join(", ")].filter(Boolean).join(" · ")}</p>
                {links.length ? (
                  <div className="tag-list">
                    {links.map((link) => (
                      <span className="note-block-project-link" key={link.link_id}>
                        <StatusBadge>{link.project_name || link.project_id} · {link.link_type}</StatusBadge>
                        {link.project_status !== "archived" && link.project_status !== "unavailable" ? (
                          <button className="reader-control reader-control--secondary" type="button" disabled={linkStatus === "saving"} onClick={() => removeProjectLink(link)}><Unlink size={14} />Unlink</button>
                        ) : null}
                      </span>
                    ))}
                  </div>
                ) : <p className="muted-text">Not linked to a Project.</p>}
                <div className="reader-editor__actions">
                  <button className="reader-control reader-control--secondary" type="button" onClick={() => beginEdit(block)}><Edit3 size={15} />Edit</button>
                  <button className="reader-control reader-control--secondary" type="button" onClick={() => setLinkingBlockId((current) => current === block.id ? "" : block.id)}><Link2 size={15} />Link to Project</button>
                </div>
                {linkingBlockId === block.id ? (
                  <form className="project-link-form" onSubmit={addProjectLink}>
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
            <StatusBadge tone={editor.status === "conflict" || editor.status === "error" ? "danger" : editor.status === "saved" ? "accent" : "neutral"}>{statusLabel(editor.status)}</StatusBadge>
          </div>
          <label className={`reader-field ${changedFields.includes("block_type") ? "reader-field--changed" : ""}`}><span>Block type{changedFields.includes("block_type") ? " (changed)" : ""}</span><select value={editor.draft.block_type} disabled={editor.status === "saving"} onChange={(event) => updateDraft("block_type", event.target.value as NoteBlockType)}>{BLOCK_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
          <label className={`reader-field ${changedFields.includes("title") ? "reader-field--changed" : ""}`}><span>Title{changedFields.includes("title") ? " (changed)" : ""}</span><input maxLength={1000} value={editor.draft.title} disabled={editor.status === "saving"} onChange={(event) => updateDraft("title", event.target.value)} /></label>
          <label className={`reader-field ${changedFields.includes("text") ? "reader-field--changed" : ""}`}><span>Text{changedFields.includes("text") ? " (changed)" : ""}</span><textarea rows={8} maxLength={100000} value={editor.draft.text} disabled={editor.status === "saving"} onChange={(event) => updateDraft("text", event.target.value)} /></label>
          <div className="project-form-grid">
            <label className={`reader-field ${changedFields.includes("page") ? "reader-field--changed" : ""}`}><span>Page</span><input maxLength={100} value={editor.draft.page} onChange={(event) => updateDraft("page", event.target.value)} /></label>
            <label className={`reader-field ${changedFields.includes("figure") ? "reader-field--changed" : ""}`}><span>Figure</span><input maxLength={500} value={editor.draft.figure} onChange={(event) => updateDraft("figure", event.target.value)} /></label>
          </div>
          <label className={`reader-field ${changedFields.includes("quote") ? "reader-field--changed" : ""}`}><span>Quote</span><textarea rows={4} maxLength={100000} value={editor.draft.quote} onChange={(event) => updateDraft("quote", event.target.value)} /></label>
          <label className={`reader-field ${changedFields.includes("tags") ? "reader-field--changed" : ""}`}><span>Tags (comma separated)</span><input value={tagDraft} onChange={(event) => { const value = event.target.value; setTagDraft(value); updateDraft("tags", value.split(",").map((tag) => tag.trim()).filter(Boolean)); }} /></label>
          <p className="reader-editor__status" role="status">{editor.message || `${changedFields.length} changed field${changedFields.length === 1 ? "" : "s"}.`}</p>
          <div className="reader-editor__actions">
            <button className="reader-control" type="submit" disabled={editor.status === "saving"}><Save size={15} />{editor.status === "saving" ? "Saving…" : "Save Note Block"}</button>
            <button className="reader-control reader-control--secondary" type="button" disabled={editor.status === "saving"} onClick={() => { setEditor(null); setTagDraft(""); }}><X size={15} />Cancel</button>
            {editor.status === "conflict" ? <button className="reader-control reader-control--secondary" type="button" onClick={() => void loadCollection({ preserveDraft: true })}><RotateCcw size={15} />Reload current collection and keep draft</button> : null}
          </div>
        </form>
      ) : null}
    </section>
  );
}
