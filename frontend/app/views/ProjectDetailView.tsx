"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { DetailPanel } from "../components/DetailPanel";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";

export function ProjectDetailView({ projectId }: { projectId: string }) {
  const resource = useApiResource(
    `project:${projectId}`,
    () => apiClient.getProject(projectId, { linksLimit: 100 }),
  );
  return (
    <div className="page-stack">
      <Link className="back-link" href="/projects"><ArrowLeft size={15} />Back to Projects</Link>
      {resource.status === "loading" ? <LoadingState label="Loading Project detail" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Project read model unavailable" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <EmptyState title="Project not found" description="The requested Project identity is not present in the local read model." /> : null}
      {resource.status === "success" ? (
        <>
          <PageHeader
            eyebrow="Project detail"
            title={resource.data.name}
            description={resource.data.description || "No description is stored for this Project."}
            actions={<div className="badge-row"><StatusBadge tone="accent">{resource.data.status}</StatusBadge><StatusBadge>{resource.data.priority}</StatusBadge></div>}
          />
          <div className="detail-grid">
            <Section title="Project metadata" description="Allowlisted values from the stored Project record.">
              <dl className="metadata-list">
                <div><dt>Project ID</dt><dd className="mono-id">{resource.data.project_id}</dd></div>
                <div><dt>Created</dt><dd>{resource.data.created_at}</dd></div>
                <div><dt>Updated</dt><dd>{resource.data.updated_at}</dd></div>
                <div><dt>Total links</dt><dd>{resource.data.link_count}</dd></div>
              </dl>
              <div className="tag-list project-tag-row">
                {resource.data.tags.length
                  ? resource.data.tags.map((tag) => <StatusBadge key={tag}>{tag}</StatusBadge>)
                  : <span className="muted-text">No Project tags are stored.</span>}
              </div>
            </Section>
            <DetailPanel title="Link state">
              <dl className="metadata-list metadata-list--compact">
                <div><dt>Paper links</dt><dd>{resource.data.linked_paper_count}</dd></div>
                <div><dt>Orphaned papers</dt><dd>{resource.data.orphaned_link_count}</dd></div>
                <div><dt>Shown</dt><dd>{resource.data.links.length} of {resource.data.links_total}</dd></div>
              </dl>
              {resource.data.links_has_more ? <p className="deferred-note">Only the first bounded page of links is shown.</p> : null}
            </DetailPanel>
          </div>
          <Section title="Linked papers" description="Stored link types and allowlisted paper metadata; missing targets remain explicit.">
            {resource.data.links.length === 0 ? (
              <EmptyState title="No Project links" description="This Project has no stored links." />
            ) : (
              <DataTableShell label="Project links">
                <table>
                  <thead><tr><th>Paper</th><th>Link type</th><th>Target state</th><th>Author</th><th>Year</th><th>Reading status</th></tr></thead>
                  <tbody>
                    {resource.data.links.map((link) => (
                      <tr key={link.link_id}>
                        <td>
                          {link.paper ? (
                            <Link className="paper-link" href={`/papers/${encodeURIComponent(link.paper.paper_id)}`}>
                              {link.paper.title || "Stored title unavailable"}
                              <small className="mono-id">{link.paper.paper_id}</small>
                            </Link>
                          ) : link.target_type === "paper" ? (
                            <span className="paper-link">
                              Linked paper unavailable
                              <small className="mono-id">{link.paper_id}</small>
                            </span>
                          ) : (
                            <span className="muted-text">Non-paper Project link</span>
                          )}
                        </td>
                        <td>{link.link_type}</td>
                        <td><StatusBadge tone={link.target_state === "available" ? "healthy" : link.target_state === "orphaned" ? "warning" : "neutral"}>{link.target_state}</StatusBadge></td>
                        <td>{link.paper?.first_author || "Not stored"}</td>
                        <td>{link.paper?.year || "Not stored"}</td>
                        <td>{link.paper ? <StatusBadge>{link.paper.status || "Not stored"}</StatusBadge> : <span className="muted-text">Unavailable</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </DataTableShell>
            )}
          </Section>
        </>
      ) : null}
    </div>
  );
}
