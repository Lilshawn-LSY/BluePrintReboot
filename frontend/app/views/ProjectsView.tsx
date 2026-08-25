"use client";

import { Plus, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { SaveStatus } from "../components/SaveStatus";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";
import { formatUiDate } from "../lib/presentation";
import type { EditableProjectMetadata, EditableProjectStatus, ProjectPriority } from "../lib/api/types";
import {
  beginRevisionSave,
  completeRevisionSave,
  createRevisionDraftState,
  draftStorageKey,
  editRevisionDraft,
  failRevisionSave,
  persistRevisionDraft,
  readPersistentRevisionDraft,
} from "../lib/drafts/revision-draft.mjs";

const EMPTY_PROJECT: EditableProjectMetadata = {
  name: "",
  description: "",
  status: "active",
  priority: "normal",
  tags: [],
};

type ProjectCreateDraft = { project: EditableProjectMetadata; tagText: string };

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

function parsedTags(value: string): string[] {
  return value.split(",").map((tag) => tag.trim()).filter(Boolean);
}

export function ProjectsView() {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const pageSize = 50;
  const resource = useApiResource(
    `projects:${offset}`,
    () => apiClient.getProjects({ limit: pageSize, offset }),
  );
  const createDraftKey = draftStorageKey("project-create", "new");
  const [createState, setCreateState] = useState(() => createRevisionDraftState<ProjectCreateDraft>({
    draft: { project: EMPTY_PROJECT, tagText: "" },
    revision: "",
    record: readPersistentRevisionDraft(browserStorage(), draftStorageKey("project-create", "new")),
  }));
  const [showCreate, setShowCreate] = useState(() => !Object.is(createState.draft, createState.baseline) && JSON.stringify(createState.draft) !== JSON.stringify(createState.baseline));
  const [draftStorageReady, setDraftStorageReady] = useState(false);
  const dirtyCreate = showCreate && JSON.stringify(createState.draft) !== JSON.stringify(createState.baseline);

  useEffect(() => {
    const restored = createRevisionDraftState<ProjectCreateDraft>({
      draft: { project: EMPTY_PROJECT, tagText: "" },
      revision: "",
      record: readPersistentRevisionDraft(browserStorage(), createDraftKey),
    });
    setCreateState(restored);
    setShowCreate(JSON.stringify(restored.draft) !== JSON.stringify(restored.baseline));
    setDraftStorageReady(true);
  }, [createDraftKey]);

  useEffect(() => {
    if (!draftStorageReady) return;
    persistRevisionDraft(browserStorage(), createDraftKey, createState);
  }, [createDraftKey, createState, draftStorageReady]);

  function updateCreate(update: (state: typeof createState) => typeof createState) {
    setCreateState((current) => {
      const next = update(current);
      if (draftStorageReady) persistRevisionDraft(browserStorage(), createDraftKey, next);
      return next;
    });
  }

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirtyCreate) return;
      event.preventDefault();
    };
    const warnNavigation = (event: globalThis.MouseEvent) => {
      if (
        !dirtyCreate
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
      if (anchor && !window.confirm("Leave Projects? Your locally preserved Project draft will remain available.")) {
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
  }, [dirtyCreate]);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const started = beginRevisionSave(createState);
    if (!started.request) return;
    const request = started.request;
    updateCreate(() => ({ ...started.state, saveState: "saving", lastError: "" }));
    try {
      const response = await apiClient.createProject({ ...request.draft.project, tags: parsedTags(request.draft.tagText) });
      updateCreate((current) => {
        const saved = completeRevisionSave(current, request.token, {
          value: {
            project: {
              name: response.project.name,
              description: response.project.description,
              status: response.project.status === "archived" ? "active" : response.project.status,
              priority: response.project.priority,
              tags: [...response.project.tags],
            },
            tagText: response.project.tags.join(", "),
          },
          revision: response.project.project_revision,
        });
        if (saved.saveState !== "saved") {
          const transferred = createRevisionDraftState({
            draft: saved.draft.project,
            baseline: saved.baseline.project,
            revision: saved.revision,
          });
          persistRevisionDraft(
            browserStorage(),
            draftStorageKey("project-metadata", response.project.project_id),
            {
              ...transferred,
              draft: saved.draft.project,
              baseline: saved.baseline.project,
              remote: saved.remote.project,
              remoteRevision: saved.remoteRevision,
              generation: saved.generation,
              saveState: "unsaved",
            },
          );
          return saved;
        }
        router.push(`/projects/${encodeURIComponent(response.project.project_id)}`);
        return saved;
      });
    } catch (error) {
      updateCreate((current) => ({
        ...failRevisionSave(current, request.token, error instanceof ApiClientError ? error.kind : "error"),
        lastError: error instanceof ApiClientError ? error.message : "The Project could not be created.",
      }));
    }
  }

  function closeCreate() {
    setShowCreate(false);
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Projects"
        description="Organize related papers and note blocks."
        actions={(
          <button className="reader-control" type="button" onClick={() => setShowCreate(true)} disabled={showCreate}>
            <Plus size={15} />Create Project
          </button>
        )}
      />
      {showCreate ? (
        <Section title="Create Project" description="Nothing is written until you choose Create. Project IDs and timestamps are generated by the service.">
          <form className="project-command-panel" onSubmit={createProject}>
            <div className="project-form-grid">
              <label className="reader-field">
                <span>Name</span>
                <input
                  required
                  maxLength={200}
                  value={createState.draft.project.name}
                  onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, project: { ...current.draft.project, name: event.target.value } }))}
                />
              </label>
              <label className="reader-field">
                <span>Description</span>
                <textarea
                  rows={4}
                  maxLength={5000}
                  value={createState.draft.project.description}
                  onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, project: { ...current.draft.project, description: event.target.value } }))}
                />
              </label>
              <label className="reader-field">
                <span>Status</span>
                <select
                  value={createState.draft.project.status}
                  onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, project: { ...current.draft.project, status: event.target.value as EditableProjectStatus } }))}
                >
                  <option value="active">Active</option>
                  <option value="paused">Paused</option>
                  <option value="done">Done</option>
                </select>
              </label>
              <label className="reader-field">
                <span>Priority</span>
                <select
                  value={createState.draft.project.priority}
                  onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, project: { ...current.draft.project, priority: event.target.value as ProjectPriority } }))}
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label className="reader-field project-form-wide">
                <span>Tags (comma separated)</span>
                <input
                  maxLength={2524}
                  value={createState.draft.tagText}
                  onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, tagText: event.target.value }))}
                />
              </label>
            </div>
            <p className="reader-editor__status" role="status">
              {createState.lastError || (createState.saveState === "offline" ? "The local API is unavailable. Your Project draft is preserved locally." : "")}
            </p>
            <div className="reader-editor__actions">
              <SaveStatus state={createState.saveState} />
              <button className="reader-control" type="submit" disabled={Boolean(createState.activeSave) || !dirtyCreate}>
                {createState.saveState === "saving" ? "Creating Project…" : "Create Project"}
              </button>
              <button className="reader-control reader-control--secondary" type="button" onClick={closeCreate} disabled={Boolean(createState.activeSave)}>
                <X size={15} />Close
              </button>
            </div>
          </form>
        </Section>
      ) : null}
      {resource.status === "loading" ? <LoadingState label="Loading Projects" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Project read model unavailable" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <ErrorState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "success" ? (
        <Section title="Projects" description={`${resource.data.total} Project${resource.data.total === 1 ? "" : "s"}.`}>
          {resource.data.items.length === 0 ? (
            <EmptyState title="No Projects" description="The local Project store is empty. This view never substitutes sample Projects." />
          ) : (
            <>
              <DataTableShell label="Stored Projects">
                <table>
                <thead><tr><th>Project</th><th>Status</th><th>Priority</th><th>Tags</th><th>Paper links</th><th>Note Block links</th><th>Updated</th></tr></thead>
                <tbody>
                  {resource.data.items.map((project) => (
                    <tr key={project.project_id}>
                      <td>
                        <Link className="paper-link" href={`/projects/${encodeURIComponent(project.project_id)}`}>{project.name}</Link>
                      </td>
                      <td><StatusBadge tone={project.status === "active" ? "accent" : "neutral"}>{project.status}</StatusBadge></td>
                      <td>{project.priority}</td>
                      <td>
                        <div className="tag-list">
                          {project.tags.length
                            ? project.tags.map((tag) => <StatusBadge key={tag}>{tag}</StatusBadge>)
                            : <span className="muted-text">None stored</span>}
                        </div>
                      </td>
                      <td>{project.linked_paper_count}</td>
                      <td>{project.linked_note_block_count}</td>
                      <td>{formatUiDate(project.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
                </table>
              </DataTableShell>
              <div className="reader-editor__actions" aria-label="Project pages">
                <button className="reader-control reader-control--secondary" type="button" disabled={resource.data.offset === 0} onClick={() => setOffset(Math.max(0, resource.data.offset - pageSize))}>Previous</button>
                <span className="muted-text">Showing {resource.data.offset + 1}–{resource.data.offset + resource.data.items.length} of {resource.data.total}</span>
                <button className="reader-control reader-control--secondary" type="button" disabled={!resource.data.has_more} onClick={() => setOffset(resource.data.offset + resource.data.items.length)}>Next</button>
              </div>
            </>
          )}
        </Section>
      ) : null}
    </div>
  );
}
