"use client";

import { Archive, ArrowLeft, Edit3, Link2, RotateCcw, Save, Unlink, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { DetailPanel } from "../components/DetailPanel";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";
import {
  applyProjectCommandResult,
  changedProjectFields,
  createProjectEditorState,
  preserveProjectDraftAfterFailure,
  resetProjectDraft,
} from "../lib/projects/editor-state.mjs";
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

function ProjectWorkspace({ snapshot }: { snapshot: ProjectDetail }) {
  const [project, setProject] = useState(snapshot);
  const [editor, setEditor] = useState(() => createProjectEditorState(snapshot));
  const [tagDraft, setTagDraft] = useState(snapshot.tags.join(", "));
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
      if (anchor && !window.confirm("Leave this Project and discard the unsaved metadata draft?")) {
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
    if (dirty && !window.confirm("Reload the current Project and discard your preserved draft?")) return;
    try {
      const current = await apiClient.getCompleteProject(project.project_id);
      setProject(current);
      setEditor(createProjectEditorState(current));
      setTagDraft(current.tags.join(", "));
      setEditing(false);
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
    const changes = Object.fromEntries(
      dirtyFields.map((field) => [field, editor.draft[field as keyof typeof editor.draft]]),
    );
    setEditor((current) => ({ ...current, status: "saving", message: "Saving Project metadata…" }));
    try {
      const response = await apiClient.updateProject(project.project_id, changes, editor.revision);
      setProject((current) => ({ ...current, ...response.project }));
      setEditor((current) => applyProjectCommandResult(current, response));
      setTagDraft(response.project.tags.join(", "));
      setEditing(false);
    } catch (error) {
      const kind = error instanceof ApiClientError ? error.kind : "error";
      setEditor((current) => preserveProjectDraftAfterFailure(current, kind));
    }
  }

  async function archiveProject() {
    if (!window.confirm("Archive this Project? This does not delete the Project, its Paper links, or any Paper.")) return;
    setEditor((current) => ({ ...current, status: "saving", message: "Archiving Project…" }));
    try {
      const response = await apiClient.archiveProject(project.project_id, project.project_revision);
      setProject((current) => ({ ...current, ...response.project }));
      setEditor((current) => applyProjectCommandResult(current, response));
      setEditing(false);
    } catch (error) {
      const kind = error instanceof ApiClientError ? error.kind : "error";
      setEditor((current) => preserveProjectDraftAfterFailure(current, kind));
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
      <PageHeader
        eyebrow="Project detail"
        title={project.name}
        description={project.description || "No description is stored for this Project."}
        actions={<div className="badge-row"><StatusBadge tone={archived ? "neutral" : "accent"}>{project.status}</StatusBadge><StatusBadge>{project.priority}</StatusBadge><StatusBadge>{project.linked_paper_count} Papers</StatusBadge><StatusBadge>{project.linked_note_block_count} Note Blocks</StatusBadge></div>}
      />
      {!archived ? (
        <Section title="Project commands" description="Changes are explicit, revision-checked, and never autosaved.">
          {editing ? (
            <form className="project-command-panel" onSubmit={saveProject}>
              <div className="project-form-grid">
                <label className={`reader-field ${dirtyFields.includes("name") ? "reader-field--changed" : ""}`}>
                  <span>Name</span>
                  <input
                    required
                    maxLength={200}
                    value={editor.draft.name}
                    onChange={(event) => setEditor((current) => ({ ...current, draft: { ...current.draft, name: event.target.value }, status: "dirty" }))}
                  />
                </label>
                <label className={`reader-field ${dirtyFields.includes("description") ? "reader-field--changed" : ""}`}>
                  <span>Description</span>
                  <textarea
                    rows={5}
                    maxLength={5000}
                    value={editor.draft.description}
                    onChange={(event) => setEditor((current) => ({ ...current, draft: { ...current.draft, description: event.target.value }, status: "dirty" }))}
                  />
                </label>
                <label className={`reader-field ${dirtyFields.includes("status") ? "reader-field--changed" : ""}`}>
                  <span>Status</span>
                  <select
                    value={editor.draft.status}
                    onChange={(event) => setEditor((current) => ({ ...current, draft: { ...current.draft, status: event.target.value as EditableProjectStatus }, status: "dirty" }))}
                  >
                    <option value="active">Active</option>
                    <option value="paused">Paused</option>
                    <option value="done">Done</option>
                  </select>
                </label>
                <label className={`reader-field ${dirtyFields.includes("priority") ? "reader-field--changed" : ""}`}>
                  <span>Priority</span>
                  <select
                    value={editor.draft.priority}
                    onChange={(event) => setEditor((current) => ({ ...current, draft: { ...current.draft, priority: event.target.value as ProjectPriority }, status: "dirty" }))}
                  >
                    <option value="low">Low</option>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                  </select>
                </label>
                <label className={`reader-field project-form-wide ${dirtyFields.includes("tags") ? "reader-field--changed" : ""}`}>
                  <span>Tags (comma separated)</span>
                  <input
                    maxLength={2524}
                  value={tagDraft}
                  onChange={(event) => {
                    const value = event.target.value;
                    setTagDraft(value);
                    setEditor((current) => ({
                      ...current,
                      draft: {
                        ...current.draft,
                        tags: value.split(",").map((tag) => tag.trim()).filter(Boolean),
                      },
                      status: "dirty",
                    }));
                  }}
                  />
                </label>
              </div>
              <p className="reader-editor__status" role="status">{editor.message || (dirty ? `${dirtyFields.length} field${dirtyFields.length === 1 ? "" : "s"} changed.` : "No unsaved changes.")}</p>
              <div className="reader-editor__actions">
                <button className="reader-control" type="submit" disabled={editor.status === "saving" || !dirty}><Save size={15} />Save Project</button>
                <button
                  className="reader-control reader-control--secondary"
                  type="button"
                  onClick={() => {
                    if (editor.status === "conflict") {
                      void reloadProject();
                      return;
                    }
                    setTagDraft(editor.baseline.tags.join(", "));
                    setEditor((current) => resetProjectDraft(current));
                    setEditing(false);
                  }}
                  disabled={editor.status === "saving"}
                ><X size={15} />Cancel</button>
                {editor.status === "conflict" ? (
                  <button className="reader-control reader-control--secondary" type="button" onClick={() => reloadProject()}>
                    <RotateCcw size={15} />Reload current Project
                  </button>
                ) : null}
              </div>
            </form>
          ) : (
            <div className="reader-editor__actions">
              <button className="reader-control" type="button" onClick={() => setEditing(true)}><Edit3 size={15} />Edit Project</button>
              <button className="reader-control reader-control--danger" type="button" onClick={archiveProject}><Archive size={15} />Archive Project</button>
              {editor.message ? <span className="reader-editor__status" role="status">{editor.message}</span> : null}
            </div>
          )}
        </Section>
      ) : (
        <div className="project-archived-note">This Project is archived. Metadata and link write controls are unavailable; stored Paper and Note Block links remain readable.</div>
      )}
      <div className="detail-grid">
        <Section title="Project metadata" description="Allowlisted values from the stored Project record.">
          <dl className="metadata-list">
            <div><dt>Project ID</dt><dd className="mono-id">{project.project_id}</dd></div>
            <div><dt>Created</dt><dd>{project.created_at}</dd></div>
            <div><dt>Updated</dt><dd>{project.updated_at}</dd></div>
            <div><dt>Total links</dt><dd>{project.link_count}</dd></div>
          </dl>
          <div className="tag-list project-tag-row">
            {project.tags.length
              ? project.tags.map((tag) => <StatusBadge key={tag}>{tag}</StatusBadge>)
              : <span className="muted-text">No Project tags are stored.</span>}
          </div>
        </Section>
        <DetailPanel title="Workspace links">
          <dl className="metadata-list metadata-list--compact">
            <div><dt>Paper links</dt><dd>{project.linked_paper_count}</dd></div>
            <div><dt>Note Block links</dt><dd>{project.linked_note_block_count}</dd></div>
            <div><dt>Orphaned links</dt><dd>{project.orphaned_link_count}</dd></div>
            <div><dt>Shown</dt><dd>{project.links.length} of {project.links_total}</dd></div>
          </dl>
        </DetailPanel>
      </div>
      {!archived && !dirty ? (
        <Section title="Add a Paper link" description="Choose any existing Paper from the paginated local Paper index. No Paper or Note Block is created.">
          <form className="project-link-form" onSubmit={addPaperLink}>
            {paperPicker.status === "loading" ? <span className="muted-text">Loading existing Papers…</span> : null}
            {paperPicker.status === "error" || paperPicker.status === "unavailable" ? (
              <span className="reader-editor__actions">
                <span className="reader-editor__status">{paperPicker.message}</span>
                <button
                  className="reader-control reader-control--secondary"
                  type="button"
                  onClick={() => {
                    setPaperPicker({ status: "loading" });
                    setPaperPickerAttempt((current) => current + 1);
                  }}
                >Retry Paper picker</button>
              </span>
            ) : null}
            {paperPicker.status === "ready" && paperPicker.data.length === 0 ? (
              <span className="muted-text">No existing Papers are available to link.</span>
            ) : null}
            {paperPicker.status === "ready" && paperPicker.data.length > 0 ? (
              <>
                <label className="reader-field">
                  <span>Existing Paper</span>
                  <select value={paperId} onChange={(event) => {
                    const nextPaperId = event.target.value;
                    setPaperId(nextPaperId);
                    setNoteBlockId("");
                    setNoteBlockPicker({ status: "loading", paperId: nextPaperId });
                  }}>
                    {paperPicker.data.map((paper) => (
                      <option key={paper.paper_id} value={paper.paper_id}>
                        {paper.title || paper.paper_id}{paper.archived ? " (archived Paper)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="reader-field">
                  <span>Link type</span>
                  <select value={linkType} onChange={(event) => setLinkType(event.target.value as ProjectLinkType)}>
                    {LINK_TYPES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </label>
                <button className="reader-control" type="submit" disabled={linkStatus === "saving" || !paperId}><Link2 size={15} />Add Paper link</button>
              </>
            ) : null}
          </form>
          <p className="reader-editor__status" role="status">{linkMessage}</p>
          {linkStatus === "conflict" ? (
            <button className="reader-control reader-control--secondary" type="button" onClick={() => reloadProject()}>
              <RotateCcw size={15} />Reload current Project
            </button>
          ) : null}
        </Section>
      ) : !archived ? (
        <div className="project-archived-note">Save or cancel the metadata draft before changing Project links.</div>
      ) : null}
      {!archived && !dirty ? (
        <Section title="Add an existing Note Block" description="Choose a source Paper, then one of its stored Note Blocks and an allowlisted link type. Nothing creates or edits a Note Block.">
          <form className="project-link-form" onSubmit={addNoteBlockLink}>
            {paperPicker.status === "loading" ? <span className="muted-text">Loading existing Papers…</span> : null}
            {paperPicker.status === "error" || paperPicker.status === "unavailable" ? (
              <span className="reader-editor__actions">
                <span className="reader-editor__status">{paperPicker.message}</span>
                <button
                  className="reader-control reader-control--secondary"
                  type="button"
                  onClick={() => {
                    setPaperPicker({ status: "loading" });
                    setPaperPickerAttempt((current) => current + 1);
                  }}
                >Retry Paper picker</button>
              </span>
            ) : null}
            {paperPicker.status === "ready" && paperPicker.data.length === 0 ? (
              <span className="muted-text">No existing Papers are available; a source Paper is required to link a Note Block.</span>
            ) : null}
            {paperPicker.status === "ready" && paperPicker.data.length > 0 ? (
              <>
                <label className="reader-field">
                  <span>Source Paper</span>
                  <select value={paperId} onChange={(event) => {
                    const nextPaperId = event.target.value;
                    setPaperId(nextPaperId);
                    setNoteBlockId("");
                    setNoteBlockPicker({ status: "loading", paperId: nextPaperId });
                  }}>
                    {paperPicker.data.map((paper) => (
                      <option key={paper.paper_id} value={paper.paper_id}>
                        {paper.title || paper.paper_id}{paper.archived ? " (archived Paper)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                {noteBlockPickerLoading ? <span className="muted-text">Loading existing Note Blocks for the selected Paper…</span> : null}
                {noteBlockPickerFailure ? (
                  <span className="reader-editor__actions">
                    <span className="reader-editor__status">{noteBlockPickerFailure.message}</span>
                    <button
                      className="reader-control reader-control--secondary"
                      type="button"
                      onClick={() => {
                        setNoteBlockPicker({ status: "loading", paperId });
                        setNoteBlockPickerAttempt((current) => current + 1);
                      }}
                    >Retry Note Block picker</button>
                  </span>
                ) : null}
                {readyNoteBlockPicker && readyNoteBlockPicker.data.items.length === 0 ? (
                  <span className="muted-text">This Paper has no stored Note Blocks to link.</span>
                ) : null}
                {readyNoteBlockPicker && readyNoteBlockPicker.data.items.length > 0 ? (
                  <>
                    <label className="reader-field">
                      <span>Existing Note Block</span>
                      <select value={noteBlockId} onChange={(event) => setNoteBlockId(event.target.value)}>
                        {readyNoteBlockPicker.data.items.map((block) => (
                          <option key={block.id} value={block.id}>
                            {block.title || `${block.block_type} Note Block`}{block.page ? ` · Page ${block.page}` : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="reader-field">
                      <span>Link type</span>
                      <select value={linkType} onChange={(event) => setLinkType(event.target.value as ProjectLinkType)}>
                        {LINK_TYPES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                      </select>
                    </label>
                    <button className="reader-control" type="submit" disabled={linkStatus === "saving" || !paperId || !noteBlockId}><Link2 size={15} />Add Note Block link</button>
                  </>
                ) : null}
              </>
            ) : null}
          </form>
          <p className="reader-editor__status" role="status">{linkMessage}</p>
          {linkStatus === "conflict" ? (
            <button className="reader-control reader-control--secondary" type="button" onClick={() => reloadProject()}>
              <RotateCcw size={15} />Reload current Project
            </button>
          ) : null}
        </Section>
      ) : null}
      <Section title="Linked Papers" description="Stored Paper links remain distinct from structured Note Block links; missing targets are never repaired automatically.">
        {paperLinks.length === 0 ? (
          <EmptyState title="No linked Papers" description="This Project has no linked Papers." />
        ) : (
          <DataTableShell label="Linked Papers">
            <table>
              <thead><tr><th>Paper</th><th>Link type</th><th>Target state</th><th>Source details</th><th>Action</th></tr></thead>
              <tbody>
                {paperLinks.map((link) => (
                  <tr key={link.link_id}>
                    <td>
                      {link.paper ? (
                        <Link className="paper-link" href={`/papers/${encodeURIComponent(link.paper.paper_id)}`}>
                          {link.paper.title || "Stored title unavailable"}
                          <small className="mono-id">{link.paper.paper_id}</small>
                        </Link>
                      ) : (
                        <span className="paper-link">
                          Linked paper unavailable
                          <small className="mono-id">{link.paper_id}</small>
                        </span>
                      )}
                    </td>
                    <td>{link.link_type}</td>
                    <td><StatusBadge tone={link.target_state === "available" ? "healthy" : link.target_state.startsWith("orphaned") ? "warning" : "neutral"}>{link.target_state}</StatusBadge></td>
                    <td>{link.paper ? `${link.paper.first_author || "Author not stored"} · ${link.paper.year || "Year not stored"}` : <span className="muted-text">Unavailable</span>}</td>
                    <td>
                      {!archived ? (
                        <button
                          className="reader-control reader-control--secondary"
                          type="button"
                          onClick={() => removePaperLink(link.link_id, link.paper?.title || link.paper_id)}
                          disabled={linkStatus === "saving" || dirty}
                        ><Unlink size={15} />Remove link</button>
                      ) : <span className="muted-text">Read only</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DataTableShell>
        )}
      </Section>
      <Section title="Linked Note Blocks" description="Stored structured Note Block links retain their source-Paper identity and explicit target state.">
        {noteBlockLinks.length === 0 ? (
          <EmptyState title="No linked Note Blocks" description="This Project has no linked Note Blocks." />
        ) : (
          <DataTableShell label="Linked Note Blocks">
            <table>
              <thead><tr><th>Note Block</th><th>Link type</th><th>Target state</th><th>Source details</th><th>Action</th></tr></thead>
              <tbody>
                {noteBlockLinks.map((link) => (
                  <tr key={link.link_id}>
                    <td>
                      {link.note_block ? (
                        <Link className="paper-link" href={`/papers/${encodeURIComponent(link.note_block.paper_id)}/reader?noteBlock=${encodeURIComponent(link.note_block.block_id)}`}>
                          {link.note_block.title || `${link.note_block.block_type} Note Block`}
                          <small>{link.note_block.text_preview || "No text preview"}</small>
                          <small className="mono-id">{link.note_block.block_id}</small>
                        </Link>
                      ) : link.target_state === "orphaned_note_block" ? (
                        <Link className="paper-link" href={`/papers/${encodeURIComponent(link.paper_id)}/reader?noteBlock=${encodeURIComponent(link.target_id)}`}>
                          Missing linked Note Block
                          <small className="mono-id">{link.target_id}</small>
                        </Link>
                      ) : (
                        <span className="paper-link">
                          Linked Note Block unavailable
                          <small className="mono-id">{link.target_id}</small>
                        </span>
                      )}
                    </td>
                    <td>{link.link_type}</td>
                    <td><StatusBadge tone={link.target_state === "available" ? "healthy" : link.target_state.startsWith("orphaned") ? "warning" : "neutral"}>{link.target_state}</StatusBadge></td>
                    <td>{link.note_block ? [link.note_block.source_paper_title || link.note_block.paper_id, link.note_block.page && `Page ${link.note_block.page}`, link.note_block.figure && `Figure ${link.note_block.figure}`, link.note_block.tags.join(", ")].filter(Boolean).join(" · ") : <span className="muted-text">Unavailable</span>}</td>
                    <td>
                      {!archived ? (
                        <button
                          className="reader-control reader-control--secondary"
                          type="button"
                          onClick={() => removeNoteBlockLink(link.link_id, link.note_block?.title || link.note_block?.block_type || link.link_id)}
                          disabled={linkStatus === "saving" || dirty}
                        ><Unlink size={15} />Remove link</button>
                      ) : <span className="muted-text">Read only</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DataTableShell>
        )}
      </Section>
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
      <Link className="back-link" href="/projects"><ArrowLeft size={15} />Back to Projects</Link>
      {resource.status === "loading" ? <LoadingState label="Loading Project detail" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Project read model unavailable" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <EmptyState title="Project not found" description="The requested Project identity is not present in the local read model." /> : null}
      {resource.status === "success" ? <ProjectWorkspace key={resource.data.project_revision} snapshot={resource.data} /> : null}
    </div>
  );
}
