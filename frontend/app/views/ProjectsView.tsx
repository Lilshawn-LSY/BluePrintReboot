"use client";

import { Plus, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { SaveStatus } from "../components/SaveStatus";
import { Toolbar } from "../components/Toolbar";
import { useApiResource } from "../hooks/useApiResource";
import { useDisclosureFocus } from "../hooks/useDisclosureFocus";
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
  const { triggerRef: createTriggerRef, restoreTriggerFocus } = useDisclosureFocus<HTMLButtonElement>();
  const [offset, setOffset] = useState(0);
  const pageSize = 20;
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [sort, setSort] = useState<"updated" | "name" | "priority">("updated");
  const resource = useApiResource("projects", apiClient.getAllProjects);
  const createDraftKey = draftStorageKey("project-create", "new");
  const [createState, setCreateState] = useState(() => createRevisionDraftState<ProjectCreateDraft>({
    draft: { project: EMPTY_PROJECT, tagText: "" },
    revision: "",
    record: readPersistentRevisionDraft(browserStorage(), draftStorageKey("project-create", "new")),
  }));
  const [showCreate, setShowCreate] = useState(() => !Object.is(createState.draft, createState.baseline) && JSON.stringify(createState.draft) !== JSON.stringify(createState.baseline));
  const [draftStorageReady, setDraftStorageReady] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);
  const dirtyCreate = showCreate && JSON.stringify(createState.draft) !== JSON.stringify(createState.baseline);
  const visibleProjects = useMemo(() => {
    if (resource.status !== "success") return [];
    const query = search.trim().toLocaleLowerCase();
    const priorityRank: Record<string, number> = { high: 0, normal: 1, low: 2 };
    return resource.data
      .filter((project) => (!query || [project.name, project.description, ...project.tags].join(" ").toLocaleLowerCase().includes(query)) && (!statusFilter || project.status === statusFilter) && (!priorityFilter || project.priority === priorityFilter))
      .sort((left, right) => {
        if (sort === "updated") return right.updated_at.localeCompare(left.updated_at) || left.name.localeCompare(right.name);
        if (sort === "priority") return (priorityRank[left.priority] ?? 9) - (priorityRank[right.priority] ?? 9) || left.name.localeCompare(right.name);
        return left.name.localeCompare(right.name);
      });
  }, [priorityFilter, resource, search, sort, statusFilter]);
  const pagedProjects = visibleProjects.slice(offset, offset + pageSize);

  useEffect(() => {
    const restored = createRevisionDraftState<ProjectCreateDraft>({
      draft: { project: EMPTY_PROJECT, tagText: "" },
      revision: "",
      record: readPersistentRevisionDraft(browserStorage(), createDraftKey),
    });
    setCreateState(restored);
    setShowCreate(JSON.stringify(restored.draft) !== JSON.stringify(restored.baseline));
    setDraftRestored(JSON.stringify(restored.draft) !== JSON.stringify(restored.baseline));
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
    window.addEventListener("beforeunload", warn);
    return () => {
      window.removeEventListener("beforeunload", warn);
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
    restoreTriggerFocus();
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Projects"
        description="Organize related papers and note blocks."
        actions={(
          <button ref={createTriggerRef} className="reader-control" type="button" onClick={() => setShowCreate((current) => !current)} aria-expanded={showCreate} aria-controls="create-project-panel">
            <Plus size={15} />Create Project
          </button>
        )}
      />
      {resource.status === "loading" ? <LoadingState label="Loading Projects" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Projects couldn't be loaded" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <ErrorState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "success" ? (
        <Section title="All projects" description={`${visibleProjects.length} Project${visibleProjects.length === 1 ? "" : "s"}.`}>
          <Toolbar label="Project collection filters">
            <label className="library-filter-field library-toolbar__search"><span>Search</span><span className="search-shell"><input type="search" value={search} placeholder="Name, description, or tag…" onChange={(event) => { setSearch(event.target.value); setOffset(0); }} /></span></label>
            <label className="library-filter-field"><span>Status</span><select className="library-filter" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setOffset(0); }}><option value="">All statuses</option><option value="active">Active</option><option value="paused">Paused</option><option value="done">Done</option><option value="archived">Archived</option></select></label>
            <label className="library-filter-field"><span>Priority</span><select className="library-filter" value={priorityFilter} onChange={(event) => { setPriorityFilter(event.target.value); setOffset(0); }}><option value="">All priorities</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option></select></label>
            <label className="library-filter-field"><span>Sort</span><select className="library-filter" value={sort} onChange={(event) => { setSort(event.target.value as typeof sort); setOffset(0); }}><option value="updated">Recently updated</option><option value="name">Name</option><option value="priority">Priority</option></select></label>
          </Toolbar>
          {visibleProjects.length === 0 ? (
            <EmptyState title={resource.data.length ? "No matching projects" : "No projects yet"} description={resource.data.length ? "Change the filters to see more projects." : "Create a project when you are ready to connect related work."} />
          ) : (
            <>
              <DataTableShell label="Projects">
                <table>
                <thead><tr><th>Project</th><th>Status</th><th>Priority</th><th>Tags</th><th>Paper links</th><th>Note Block links</th><th>Updated</th></tr></thead>
                <tbody>
                  {pagedProjects.map((project) => (
                    <tr key={project.project_id}>
                      <td>
                        <Link className="paper-link" href={`/projects/${encodeURIComponent(project.project_id)}`}>{project.name}</Link>
                      </td>
                      <td><StatusBadge tone={project.status === "archived" ? "warning" : "neutral"}>{project.status}</StatusBadge></td>
                      <td>{project.priority}</td>
                      <td>
                        <div className="tag-list">
                          {project.tags.length
                            ? project.tags.map((tag) => <StatusBadge presentation="chip" key={tag}>{tag}</StatusBadge>)
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
                <button className="reader-control reader-control--secondary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</button>
                <span className="muted-text">Showing {offset + 1}–{offset + pagedProjects.length} of {visibleProjects.length}</span>
                <button className="reader-control reader-control--secondary" type="button" disabled={offset + pagedProjects.length >= visibleProjects.length} onClick={() => setOffset(offset + pagedProjects.length)}>Next</button>
              </div>
            </>
          )}
        </Section>
      ) : null}
      {showCreate ? (
        <Section title="Create Project" description="Your draft stays on this device until you create the project.">
          <form id="create-project-panel" className="project-command-panel project-command-panel--disclosure" onSubmit={createProject}>
            <div className="project-form-grid">
              <label className="reader-field">
                <span>Name</span>
                <input required maxLength={200} value={createState.draft.project.name} onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, project: { ...current.draft.project, name: event.target.value } }))} />
              </label>
              <label className="reader-field">
                <span>Description</span>
                <textarea rows={4} maxLength={5000} value={createState.draft.project.description} onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, project: { ...current.draft.project, description: event.target.value } }))} />
              </label>
              <label className="reader-field">
                <span>Status</span>
                <select value={createState.draft.project.status} onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, project: { ...current.draft.project, status: event.target.value as EditableProjectStatus } }))}>
                  <option value="active">Active</option><option value="paused">Paused</option><option value="done">Done</option>
                </select>
              </label>
              <label className="reader-field">
                <span>Priority</span>
                <select value={createState.draft.project.priority} onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, project: { ...current.draft.project, priority: event.target.value as ProjectPriority } }))}>
                  <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option>
                </select>
              </label>
              <label className="reader-field project-form-wide">
                <span>Tags (comma separated)</span>
                <input maxLength={2524} value={createState.draft.tagText} onChange={(event) => updateCreate((current) => editRevisionDraft(current, { ...current.draft, tagText: event.target.value }))} />
              </label>
            </div>
            <p className="reader-editor__status" role="status">{createState.lastError || (draftRestored ? "Draft restored" : createState.saveState === "offline" ? "The local API is unavailable. Your Project draft is preserved locally." : "")}</p>
            <div className="reader-editor__actions">
              <SaveStatus state={createState.saveState} />
              <button className="reader-control" type="submit" disabled={Boolean(createState.activeSave) || !dirtyCreate}>{createState.saveState === "saving" ? "Creating Project…" : "Create Project"}</button>
              <button className="reader-control reader-control--secondary" type="button" onClick={closeCreate} disabled={Boolean(createState.activeSave)}><X size={15} />Close</button>
            </div>
          </form>
        </Section>
      ) : null}
    </div>
  );
}
