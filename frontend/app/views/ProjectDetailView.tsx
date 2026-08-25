"use client";

import { Archive, Edit3, Link2, RotateCcw, Save, Unlink, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { SaveStatus } from "../components/SaveStatus";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";
import { formatUiDate } from "../lib/presentation";
import {
  changedProjectFields,
  createProjectEditorState,
  editableProjectMetadata,
} from "../lib/projects/editor-state.mjs";
import type { ProjectEditorState } from "../lib/projects/editor-state.mjs";
import {
  applyLatestRevisionDraft,
  beginRevisionSave,
  completeRevisionSave,
  draftStorageKey,
  editRevisionDraft,
  failRevisionSave,
  keepMyRevisionDraft,
  persistRevisionDraft,
  readPersistentRevisionDraft,
  receiveRemoteRevision,
} from "../lib/drafts/revision-draft.mjs";
import type {
  EditableProjectStatus,
  NoteBlockCollection,
  PaperListItem,
  ProjectDetail,
  ProjectLinkType,
  ProjectPriority,
} from "../lib/api/types";

const LINK_TYPES: Array<{ value: ProjectLinkType; label: string }> = [
  { value: "related", label: "Related" },
  { value: "background", label: "Background" },
  { value: "key_reference", label: "Key reference" },
  { value: "supports_project", label: "Supports Project" },
  { value: "raises_question", label: "Raises question" },
  { value: "idea_for_project", label: "Idea for Project" },
];

function linkTypeLabel(value: string): string {
  return LINK_TYPES.find((option) => option.value === value)?.label ?? value.replaceAll("_", " ");
}

function targetStateTone(value: string): "healthy" | "warning" | "neutral" {
  if (value === "available") return "healthy";
  return value.startsWith("orphaned") ? "warning" : "neutral";
}

type PaperPickerState =
  | { status: "loading" }
  | { status: "ready"; data: PaperListItem[] }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string };

type NoteBlockPickerState =
  | { status: "idle" }
  | { status: "loading"; paperId: string }
  | { status: "ready"; paperId: string; data: NoteBlockCollection }
  | { status: "unavailable"; paperId: string; message: string }
  | { status: "error"; paperId: string; message: string };

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

function ProjectWorkspace({ snapshot }: { snapshot: ProjectDetail }) {
  const [project, setProject] = useState(snapshot);
  const projectDraftKey = draftStorageKey("project-metadata", snapshot.project_id);
  const [editor, setEditor] = useState(() => createProjectEditorState(
    snapshot,
    readPersistentRevisionDraft(browserStorage(), draftStorageKey("project-metadata", snapshot.project_id)),
  ));
  const [tagDraft, setTagDraft] = useState(() => editor.draft.tags.join(", "));
  const [draftStorageReady, setDraftStorageReady] = useState(false);
  const [editing, setEditing] = useState(false);
  const [paperPicker, setPaperPicker] = useState<PaperPickerState>({ status: "loading" });
  const [paperPickerAttempt, setPaperPickerAttempt] = useState(0);
  const [paperId, setPaperId] = useState("");
  const [noteBlockPicker, setNoteBlockPicker] = useState<NoteBlockPickerState>({ status: "idle" });
  const [noteBlockPickerAttempt, setNoteBlockPickerAttempt] = useState(0);
  const [noteBlockId, setNoteBlockId] = useState("");
  const [linkType, setLinkType] = useState<ProjectLinkType>("related");
  const [linkStatus, setLinkStatus] = useState<"idle" | "saving" | "conflict" | "error">("idle");
  const [linkMessage, setLinkMessage] = useState("");
  const dirtyFields = changedProjectFields(editor.draft, editor.baseline);
  const dirty = dirtyFields.length > 0;
  const archived = project.status === "archived";

  useEffect(() => {
    const restored = createProjectEditorState(
      snapshot,
      readPersistentRevisionDraft(browserStorage(), projectDraftKey),
    );
    setEditor(restored);
    setTagDraft(restored.draft.tags.join(", "));
    setDraftStorageReady(true);
  }, [projectDraftKey, snapshot]);

  useEffect(() => {
    if (!draftStorageReady) return;
    persistRevisionDraft(browserStorage(), projectDraftKey, editor);
  }, [draftStorageReady, editor, projectDraftKey]);

  function updateEditor(update: (state: ProjectEditorState) => ProjectEditorState) {
    setEditor((current) => {
      const next = update(current);
      if (draftStorageReady) persistRevisionDraft(browserStorage(), projectDraftKey, next);
      return next;
    });
  }

  useEffect(() => {
    if (archived) return;
    let active = true;
    apiClient.getAllPapers({ archiveStatus: "all" })
      .then((data) => {
        if (!active) return;
        setPaperPicker({ status: "ready", data });
        setPaperId((current) => current || data[0]?.paper_id || "");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setPaperPicker({
          status: error instanceof ApiClientError && (error.kind === "unavailable" || error.kind === "read-model")
            ? "unavailable"
            : "error",
          message: error instanceof ApiClientError
            ? error.message
            : "The Paper picker could not be loaded.",
        });
      });
    return () => { active = false; };
  }, [archived, paperPickerAttempt]);

  useEffect(() => {
    if (archived || !paperId) return;
    let active = true;
    apiClient.getNoteBlocks(paperId)
      .then((data) => {
        if (!active) return;
        setNoteBlockPicker({ status: "ready", paperId, data });
        setNoteBlockId((current) => (
          data.items.some((block) => block.id === current)
            ? current
            : data.items[0]?.id || ""
        ));
      })
      .catch((error: unknown) => {
        if (!active) return;
        setNoteBlockPicker({
          status: error instanceof ApiClientError && (error.kind === "unavailable" || error.kind === "read-model")
            ? "unavailable"
            : "error",
          paperId,
          message: error instanceof ApiClientError
            ? error.message
            : "The selected Paper's Note Blocks could not be loaded.",
        });
      });
    return () => { active = false; };
  }, [archived, noteBlockPickerAttempt, paperId]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
    };
    const warnNavigation = (event: globalThis.MouseEvent) => {
      if (
        !dirty
        || event.defaultPrevented
        || event.button !== 0
        || event.metaKey
        || event.ctrlKey
        || event.shiftKey
        || event.altKey
      ) return;
      const anchor = event.target instanceof Element
        ? event.target.closest("a[href]")
        : null;
      if (anchor && !window.confirm("Leave this Project? Your locally preserved metadata draft will remain available.")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", warnNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", warnNavigation, true);
    };
  }, [dirty]);

  async function reloadProject() {
    try {
      const current = await apiClient.getCompleteProject(project.project_id);
      setProject(current);
      updateEditor((state) => {
        const received = receiveRemoteRevision(state, {
          value: editableProjectMetadata(current),
          revision: current.project_revision,
          changedElsewhere: current.project_revision !== state.revision
            && changedProjectFields(state.draft, state.baseline).length > 0,
        });
        return {
          ...received,
          status: received.saveState === "saved" ? "clean" : "conflict",
          message: received.saveState === "saved"
            ? "Current Project loaded."
            : "The latest saved Project was loaded separately. Choose which version to keep.",
        };
      });
      if (!dirty) {
        setTagDraft(current.tags.join(", "));
        setEditing(false);
      }
      setLinkStatus("idle");
      setLinkMessage("");
      return true;
    } catch (error) {
      setLinkStatus("error");
      setLinkMessage(error instanceof ApiClientError ? error.message : "The current Project could not be reloaded.");
      return false;
    }
  }

  async function saveProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const started = beginRevisionSave(editor);
    if (!started.request) return;
    const request = started.request;
    const changes = Object.fromEntries(
      changedProjectFields(request.draft, editor.baseline).map((field) => [field, request.draft[field]]),
    );
    updateEditor(() => ({ ...started.state, status: "saving", message: "Saving Project metadata…" }));
    try {
      const response = await apiClient.updateProject(project.project_id, changes, request.revision);
      setProject((current) => ({ ...current, ...response.project }));
      updateEditor((current) => {
        const saved = completeRevisionSave(current, request.token, {
          value: editableProjectMetadata(response.project),
          revision: response.project.project_revision,
        });
        const next = {
          ...saved,
          status: saved.saveState === "saved" ? "saved" as const : "dirty" as const,
          message: saved.saveState === "saved"
            ? response.status === "no_op" ? "Project metadata already matched the saved version." : "Project metadata saved."
            : "The saved Project is current. Newer local edits are still unsaved.",
        };
        if (saved.saveState === "saved") {
          setTagDraft(response.project.tags.join(", "));
          setEditing(false);
        }
        return next;
      });
    } catch (error) {
      let latest: ProjectDetail | null = null;
      if (error instanceof ApiClientError && error.kind === "conflict") {
        try { latest = await apiClient.getCompleteProject(project.project_id); } catch { /* preserve the local draft until retry */ }
      }
      updateEditor((current) => {
        let failed = failRevisionSave(current, request.token, error instanceof ApiClientError ? error.kind : "error");
        if (latest) failed = receiveRemoteRevision(failed, {
          value: editableProjectMetadata(latest),
          revision: latest.project_revision,
          changedElsewhere: true,
        });
        return {
          ...failed,
          status: failed.saveState === "changed_elsewhere" ? "conflict" : "error",
          message: failed.saveState === "changed_elsewhere"
            ? "This Project changed elsewhere. Your local draft and the latest saved Project are both preserved."
            : failed.saveState === "offline"
              ? "The local API is unavailable. Your Project draft is preserved locally."
              : "Save failed. Your Project draft remains preserved locally.",
        };
      });
    }
  }

  async function archiveProject() {
    if (!window.confirm("Archive this Project? This does not delete the Project, its Paper links, or any Paper.")) return;
    updateEditor((current) => ({ ...current, status: "saving", saveState: "saving", message: "Archiving Project…" }));
    try {
      const response = await apiClient.archiveProject(project.project_id, project.project_revision);
      setProject((current) => ({ ...current, ...response.project }));
      updateEditor((current) => ({
        ...receiveRemoteRevision(current, {
          value: editableProjectMetadata(response.project),
          revision: response.project.project_revision,
        }),
        status: "saved",
        message: "Project archived. Existing links remain readable.",
      }));
      setEditing(false);
    } catch (error) {
      updateEditor((current) => ({
        ...current,
        saveState: error instanceof ApiClientError && error.kind === "unavailable" ? "offline" : "failed",
        status: "error",
        message: "The Project could not be archived. Your Project draft is preserved locally.",
      }));
    }
  }

  async function addPaperLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!paperId) return;
    setLinkStatus("saving");
    setLinkMessage("Adding Paper link…");
    try {
      const response = await apiClient.addProjectPaperLink(
        project.project_id,
        paperId,
        linkType,
        project.links_revision,
      );
      const refreshed = await reloadProject();
      if (refreshed) {
        setLinkStatus("idle");
        setLinkMessage(response.status === "unchanged"
          ? "That exact Paper link already exists; nothing was written."
          : "Paper link added.");
      } else {
        setLinkMessage("The Paper-link command succeeded, but the current link list could not be reloaded. Retry reload.");
      }
    } catch (error) {
      setLinkStatus(error instanceof ApiClientError && error.kind === "conflict" ? "conflict" : "error");
      setLinkMessage(error instanceof ApiClientError
        ? `${error.message} The selected Paper and link type are preserved.`
        : "The Paper link could not be added. Your selection is preserved.");
    }
  }

  async function removePaperLink(linkId: string, title: string) {
    if (!window.confirm(`Remove the Project link to “${title}”? This does not delete the Paper.`)) return;
    setLinkStatus("saving");
    setLinkMessage("Removing Paper link…");
    try {
      await apiClient.removeProjectPaperLink(project.project_id, linkId, project.links_revision);
      const refreshed = await reloadProject();
      if (refreshed) {
        setLinkStatus("idle");
        setLinkMessage("Paper link removed. The Paper was not deleted.");
      } else {
        setLinkMessage("The Paper link was removed, but the current link list could not be reloaded. Retry reload.");
      }
    } catch (error) {
      setLinkStatus(error instanceof ApiClientError && error.kind === "conflict" ? "conflict" : "error");
      setLinkMessage(error instanceof ApiClientError ? error.message : "The Paper link could not be removed.");
    }
  }

  async function removeNoteBlockLink(linkId: string, title: string) {
    if (!window.confirm(`Remove the Project link to Note Block “${title}”? This does not delete the Note Block or source Paper.`)) return;
    setLinkStatus("saving");
    setLinkMessage("Removing Note Block link…");
    try {
      await apiClient.removeProjectNoteBlockLink(project.project_id, linkId, project.links_revision);
      const refreshed = await reloadProject();
      if (refreshed) {
        setLinkStatus("idle");
        setLinkMessage("Note Block link removed. The Note Block and source Paper were not changed.");
      } else {
        setLinkMessage("The Note Block link was removed, but the current link list could not be reloaded. Retry reload.");
      }
    } catch (error) {
      setLinkStatus(error instanceof ApiClientError && error.kind === "conflict" ? "conflict" : "error");
      setLinkMessage(error instanceof ApiClientError ? error.message : "The Note Block link could not be removed.");
    }
  }

  async function addNoteBlockLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!paperId || !noteBlockId) return;
    setLinkStatus("saving");
    setLinkMessage("Adding Note Block link…");
    try {
      const response = await apiClient.addProjectNoteBlockLink(
        project.project_id,
        paperId,
        noteBlockId,
        linkType,
        project.links_revision,
      );
      const refreshed = await reloadProject();
      if (refreshed) {
        setLinkStatus("idle");
        setLinkMessage(response.status === "unchanged"
          ? "That exact Note Block link already exists; nothing was written."
          : "Note Block link added.");
      } else {
        setLinkMessage("The Note Block-link command succeeded, but the current link list could not be reloaded. Retry reload.");
      }
    } catch (error) {
      setLinkStatus(error instanceof ApiClientError && error.kind === "conflict" ? "conflict" : "error");
      setLinkMessage(error instanceof ApiClientError
        ? `${error.message} The selected Paper, Note Block, and link type are preserved.`
        : "The Note Block link could not be added. Your selection is preserved.");
    }
  }

  const paperLinks = project.links.filter((link) => link.target_type === "paper");
  const noteBlockLinks = project.links.filter((link) => link.target_type === "note_block");
  const noteBlockPickerMatchesPaper = noteBlockPicker.status !== "idle" && noteBlockPicker.paperId === paperId;
  const noteBlockPickerLoading = Boolean(paperId) && (
    !noteBlockPickerMatchesPaper || noteBlockPicker.status === "loading"
  );
  const noteBlockPickerFailure = noteBlockPickerMatchesPaper && (
    noteBlockPicker.status === "error" || noteBlockPicker.status === "unavailable"
  ) ? noteBlockPicker : null;
  const readyNoteBlockPicker = noteBlockPickerMatchesPaper && noteBlockPicker.status === "ready"
    ? noteBlockPicker
    : null;

  return (
    <>
      <Breadcrumbs items={[{ label: "Projects", href: "/projects" }, { label: project.name || "Project" }]} />
      <PageHeader title={project.name} description={project.description || "No description yet."} actions={<div className="badge-row"><StatusBadge tone={archived ? "neutral" : "accent"}>{project.status}</StatusBadge><StatusBadge>{project.priority}</StatusBadge></div>} />
      <Section title="Overview">
        <div className="project-overview">
          <dl className="project-overview__facts">
            <div><dt>Status</dt><dd><StatusBadge tone={archived ? "neutral" : "accent"}>{project.status}</StatusBadge></dd></div>
            <div><dt>Priority</dt><dd><StatusBadge>{project.priority}</StatusBadge></dd></div>
            <div><dt>Last updated</dt><dd>{formatUiDate(project.updated_at)}</dd></div>
            <div><dt>Linked material</dt><dd>{project.linked_paper_count} Papers · {project.linked_note_block_count} Note Blocks</dd></div>
          </dl>
          <div className="tag-list">{project.tags.length ? project.tags.map((tag) => <StatusBadge key={tag}>{tag}</StatusBadge>) : <span className="muted-text">No project tags yet.</span>}</div>
          {!archived && !editing ? <div className="reader-editor__actions"><button className="reader-control" type="button" onClick={() => setEditing(true)}><Edit3 size={15} />Edit Project</button><button className="reader-control reader-control--secondary" type="button" onClick={() => void reloadProject()}><RotateCcw size={15} />Reload current Project</button><button className="reader-control reader-control--danger" type="button" onClick={archiveProject}><Archive size={15} />Archive Project</button>{editor.message ? <span className="reader-editor__status" role="status">{editor.message}</span> : null}</div> : null}
          {archived ? <div className="project-archived-note">This Project is archived. Its linked Papers and Note Blocks remain available to review.</div> : null}
        </div>
      </Section>
      {!archived && editing ? <Section title="Edit Project" description="Changes are saved only when you choose Save.">
        <form className="project-command-panel" onSubmit={saveProject}>
          <div className="reader-note__heading"><span>Local draft</span><SaveStatus state={editor.saveState} /></div>
          <div className="project-form-grid">
            <label className={`reader-field ${dirtyFields.includes("name") ? "reader-field--changed" : ""}`}><span>Name</span><input required maxLength={200} value={editor.draft.name} onChange={(event) => updateEditor((current) => ({ ...editRevisionDraft(current, { ...current.draft, name: event.target.value }), status: "dirty", message: "" }))} /></label>
            <label className={`reader-field ${dirtyFields.includes("description") ? "reader-field--changed" : ""}`}><span>Description</span><textarea rows={5} maxLength={5000} value={editor.draft.description} onChange={(event) => updateEditor((current) => ({ ...editRevisionDraft(current, { ...current.draft, description: event.target.value }), status: "dirty", message: "" }))} /></label>
            <label className={`reader-field ${dirtyFields.includes("status") ? "reader-field--changed" : ""}`}><span>Status</span><select value={editor.draft.status} onChange={(event) => updateEditor((current) => ({ ...editRevisionDraft(current, { ...current.draft, status: event.target.value as EditableProjectStatus }), status: "dirty", message: "" }))}><option value="active">Active</option><option value="paused">Paused</option><option value="done">Done</option></select></label>
            <label className={`reader-field ${dirtyFields.includes("priority") ? "reader-field--changed" : ""}`}><span>Priority</span><select value={editor.draft.priority} onChange={(event) => updateEditor((current) => ({ ...editRevisionDraft(current, { ...current.draft, priority: event.target.value as ProjectPriority }), status: "dirty", message: "" }))}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>
            <label className={`reader-field project-form-wide ${dirtyFields.includes("tags") ? "reader-field--changed" : ""}`}><span>Tags (comma separated)</span><input maxLength={2524} value={tagDraft} onChange={(event) => { const value = event.target.value; setTagDraft(value); updateEditor((current) => ({ ...editRevisionDraft(current, { ...current.draft, tags: value.split(",").map((tag) => tag.trim()).filter(Boolean) }), status: "dirty", message: "" })); }} /></label>
          </div>
          <p className="reader-editor__status" role="status">{editor.message || (dirty ? `${dirtyFields.length} field${dirtyFields.length === 1 ? "" : "s"} changed.` : "No unsaved changes.")}</p>
          <div className="reader-editor__actions">
            <button className="reader-control" type="submit" disabled={Boolean(editor.activeSave) || editor.saveState === "changed_elsewhere" || !dirty}><Save size={15} />{editor.saveState === "saving" ? "Saving…" : "Save Project"}</button>
            <button className="reader-control reader-control--secondary" type="button" onClick={() => { setTagDraft(editor.baseline.tags.join(", ")); updateEditor((current) => ({ ...applyLatestRevisionDraft(current), status: "clean", message: "" })); setEditing(false); }} disabled={Boolean(editor.activeSave)}><X size={15} />Cancel</button>
            {editor.saveState === "changed_elsewhere" ? <><button className="reader-control reader-control--secondary" type="button" disabled={editor.remoteRevision === editor.revision} onClick={() => updateEditor((current) => ({ ...keepMyRevisionDraft(current), status: "dirty", message: "Your local Project draft will be saved against the latest version." }))}>Keep my draft</button><button className="reader-control reader-control--secondary" type="button" onClick={() => { if (window.confirm("Use the latest saved Project and discard the local draft?")) updateEditor((current) => ({ ...applyLatestRevisionDraft(current), status: "clean", message: "Latest saved Project in use." })); }}>Use latest saved version</button><button className="reader-control reader-control--secondary" type="button" onClick={() => void reloadProject()}><RotateCcw size={15} />Reload Project</button><details className="reader-note__conflict-review"><summary>Review local and latest</summary><h3>My draft</h3><pre>{JSON.stringify(editor.draft, null, 2)}</pre><h3>Latest saved value</h3><pre>{JSON.stringify(editor.remote, null, 2)}</pre></details></> : null}
          </div>
        </form>
      </Section> : null}
      <Section title="Linked Papers" description="Papers connected to this project.">
        {paperLinks.length === 0 ? <EmptyState title="No linked Papers" description="Add a Paper from Manage links when it becomes useful to this project." /> : <div className="project-linked-card-list">{paperLinks.map((link) => <article className="project-link-card" key={link.link_id}><div className="project-link-card__heading"><div>{link.paper ? <Link className="paper-link" href={`/papers/${encodeURIComponent(link.paper.paper_id)}`}>{link.paper.title || "Stored title unavailable"}</Link> : <strong>Linked Paper unavailable</strong>}<p>{link.paper ? `${link.paper.first_author || "Author not recorded"}${link.paper.year ? ` · ${link.paper.year}` : ""}` : "The Paper is not currently available."}</p></div><div className="badge-row"><StatusBadge>{linkTypeLabel(link.link_type)}</StatusBadge><StatusBadge tone={targetStateTone(link.target_state)}>{link.target_state.replaceAll("_", " ")}</StatusBadge></div></div>{!archived ? <div className="reader-editor__actions"><button className="reader-control reader-control--secondary" type="button" onClick={() => removePaperLink(link.link_id, link.paper?.title || "this Paper")} disabled={linkStatus === "saving" || dirty}><Unlink size={15} />Remove link</button></div> : <span className="muted-text">Read only</span>}</article>)}</div>}
      </Section>
      <Section title="Linked Note Blocks" description="Saved observations and ideas connected to this project.">
        {noteBlockLinks.length === 0 ? <EmptyState title="No linked Note Blocks" description="Add an existing Note Block from Manage links when it supports this project." /> : <div className="project-linked-card-list">{noteBlockLinks.map((link) => <article className="project-link-card" key={link.link_id}><div className="project-link-card__heading"><div>{link.note_block ? <Link className="paper-link" href={`/papers/${encodeURIComponent(link.note_block.paper_id)}/reader?noteBlock=${encodeURIComponent(link.note_block.block_id)}`}>{link.note_block.title || `${link.note_block.block_type} Note Block`}</Link> : link.target_state === "orphaned_note_block" ? <Link className="paper-link" href={`/papers/${encodeURIComponent(link.paper_id)}/reader?noteBlock=${encodeURIComponent(link.target_id)}`}>Missing linked Note Block</Link> : <strong>Linked Note Block unavailable</strong>}<p>{link.note_block ? [link.note_block.source_paper_title, link.note_block.tags.length ? link.note_block.tags.join(", ") : null, link.note_block.page && `Page ${link.note_block.page}`, link.note_block.figure && `Figure ${link.note_block.figure}`, link.note_block.text_preview].filter(Boolean).join(" · ") : "The saved Note Block is not currently available."}</p></div><div className="badge-row"><StatusBadge>{linkTypeLabel(link.link_type)}</StatusBadge><StatusBadge tone={targetStateTone(link.target_state)}>{link.target_state.replaceAll("_", " ")}</StatusBadge></div></div>{!archived ? <div className="reader-editor__actions"><button className="reader-control reader-control--secondary" type="button" onClick={() => removeNoteBlockLink(link.link_id, link.note_block?.title || link.note_block?.block_type || "this Note Block")} disabled={linkStatus === "saving" || dirty}><Unlink size={15} />Remove link</button></div> : <span className="muted-text">Read only</span>}</article>)}</div>}
      </Section>
      <details id="manage-project-links" className="project-manage-links">
        <summary>Manage links <span>Add or remove the connections above</span></summary>
        {archived ? <p className="project-archived-note">Archived Projects keep their links available for review but cannot change them.</p> : dirty ? <p className="project-archived-note">Save or cancel the Project draft before changing links.</p> : <div className="project-manage-links__content">
          <section aria-labelledby="add-paper-link"><h2 id="add-paper-link">Add Paper</h2><form className="project-link-form" onSubmit={addPaperLink}>
            {paperPicker.status === "loading" ? <span className="muted-text">Loading Papers…</span> : null}
            {paperPicker.status === "error" || paperPicker.status === "unavailable" ? <span className="reader-editor__actions"><span className="reader-editor__status">{paperPicker.message}</span><button className="reader-control reader-control--secondary" type="button" onClick={() => { setPaperPicker({ status: "loading" }); setPaperPickerAttempt((current) => current + 1); }}>Retry Papers</button></span> : null}
            {paperPicker.status === "ready" && paperPicker.data.length === 0 ? <span className="muted-text">No Papers are available to link.</span> : null}
            {paperPicker.status === "ready" && paperPicker.data.length > 0 ? <><label className="reader-field"><span>Paper</span><select value={paperId} onChange={(event) => { const nextPaperId = event.target.value; setPaperId(nextPaperId); setNoteBlockId(""); setNoteBlockPicker({ status: "loading", paperId: nextPaperId }); }}>{paperPicker.data.map((paper) => <option key={paper.paper_id} value={paper.paper_id}>{paper.title || paper.paper_id}{paper.archived ? " (archived)" : ""}</option>)}</select></label><label className="reader-field"><span>Relationship</span><select value={linkType} onChange={(event) => setLinkType(event.target.value as ProjectLinkType)}>{LINK_TYPES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><button className="reader-control" type="submit" disabled={linkStatus === "saving" || !paperId}><Link2 size={15} />Add Paper</button></> : null}
          </form></section>
          <section aria-labelledby="add-note-block-link"><h2 id="add-note-block-link">Add Note Block</h2><form className="project-link-form project-link-form--note-block" onSubmit={addNoteBlockLink}>
            {paperPicker.status === "ready" && paperPicker.data.length > 0 ? <><label className="reader-field"><span>Source Paper</span><select value={paperId} onChange={(event) => { const nextPaperId = event.target.value; setPaperId(nextPaperId); setNoteBlockId(""); setNoteBlockPicker({ status: "loading", paperId: nextPaperId }); }}>{paperPicker.data.map((paper) => <option key={paper.paper_id} value={paper.paper_id}>{paper.title || paper.paper_id}{paper.archived ? " (archived)" : ""}</option>)}</select></label>{noteBlockPickerLoading ? <span className="muted-text">Loading Note Blocks…</span> : null}{noteBlockPickerFailure ? <span className="reader-editor__actions"><span className="reader-editor__status">{noteBlockPickerFailure.message}</span><button className="reader-control reader-control--secondary" type="button" onClick={() => { setNoteBlockPicker({ status: "loading", paperId }); setNoteBlockPickerAttempt((current) => current + 1); }}>Retry Note Blocks</button></span> : null}{readyNoteBlockPicker && readyNoteBlockPicker.data.items.length === 0 ? <span className="muted-text">This Paper has no saved Note Blocks.</span> : null}{readyNoteBlockPicker && readyNoteBlockPicker.data.items.length > 0 ? <><label className="reader-field"><span>Note Block</span><select value={noteBlockId} onChange={(event) => setNoteBlockId(event.target.value)}>{readyNoteBlockPicker.data.items.map((block) => <option key={block.id} value={block.id}>{block.title || `${block.block_type} Note Block`}{block.page ? ` · Page ${block.page}` : ""}</option>)}</select></label><label className="reader-field"><span>Relationship</span><select value={linkType} onChange={(event) => setLinkType(event.target.value as ProjectLinkType)}>{LINK_TYPES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><button className="reader-control" type="submit" disabled={linkStatus === "saving" || !paperId || !noteBlockId}><Link2 size={15} />Add Note Block</button></> : null}</> : paperPicker.status === "loading" ? <span className="muted-text">Loading Papers…</span> : null}
          </form></section>
          <p className="reader-editor__status" role="status">{linkMessage}</p>
          {linkStatus === "conflict" ? <button className="reader-control reader-control--secondary" type="button" onClick={() => void reloadProject()}><RotateCcw size={15} />Reload Project</button> : null}
        </div>}
      </details>
    </>
  );
}

export function ProjectDetailView({ projectId }: { projectId: string }) {
  const resource = useApiResource(
    `project:${projectId}`,
    () => apiClient.getCompleteProject(projectId),
  );
  return (
    <div className="page-stack">
      {resource.status === "loading" ? <LoadingState label="Loading Project detail" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Project read model unavailable" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <EmptyState title="Project not found" description="The requested Project identity is not present in the local read model." /> : null}
      {resource.status === "success" ? <ProjectWorkspace key={resource.data.project_revision} snapshot={resource.data} /> : null}
    </div>
  );
}
