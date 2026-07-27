"use client";

import Link from "next/link";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";

export function ProjectsView() {
  const resource = useApiResource("projects", () => apiClient.getProjects({ limit: 100 }));
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Research organization" title="Projects" description="Browse stored research Projects and open their existing paper links. Project changes remain in Streamlit." />
      {resource.status === "loading" ? <LoadingState label="Loading Projects" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Project read model unavailable" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <ErrorState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "success" ? (
        <Section title="Stored Projects" description={`${resource.data.total} Project${resource.data.total === 1 ? "" : "s"} in deterministic name order.`}>
          {resource.data.items.length === 0 ? (
            <EmptyState title="No Projects" description="The local Project store is empty. This view never substitutes sample Projects." />
          ) : (
            <DataTableShell label="Stored Projects">
              <table>
                <thead><tr><th>Project</th><th>Status</th><th>Priority</th><th>Tags</th><th>Paper links</th><th>Updated</th></tr></thead>
                <tbody>
                  {resource.data.items.map((project) => (
                    <tr key={project.project_id}>
                      <td>
                        <Link className="paper-link" href={`/projects/${encodeURIComponent(project.project_id)}`}>
                          {project.name}
                          <small className="mono-id">{project.project_id}</small>
                        </Link>
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
                      <td>{project.updated_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DataTableShell>
          )}
        </Section>
      ) : null}
    </div>
  );
}
