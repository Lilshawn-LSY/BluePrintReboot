"use client";

import { ArrowRight, BookOpen, LibraryBig } from "lucide-react";
import Link from "next/link";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";

export function DashboardView() {
  const resource = useApiResource("dashboard", apiClient.getDashboard);
  return (
    <div className="page-stack">
      <PageHeader title="Dashboard" description="Your library at a glance." />
      {resource.status === "loading" ? <LoadingState label="Loading workspace overview" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "error" || resource.status === "not-found" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? (
        <>
          <Section title="Workspace status">
            <div className="summary-strip">
              {resource.data.health.overall_state !== "healthy" ? <div><span>Library status</span><StatusBadge tone={resource.data.health.overall_state === "blocked" ? "danger" : "warning"}>{resource.data.health.overall_state}</StatusBadge></div> : null}
              <div><span>Active papers</span><strong>{resource.data.library.active_count}</strong></div>
              <div><span>Archived</span><strong>{resource.data.library.archived_count}</strong></div>
              <div><span>Needs attention</span><strong>{resource.data.health.blocking_issues + resource.data.health.warning_count}</strong></div>
            </div>
          </Section>
          <div className="split-layout">
            <Section title="Current work" actions={<Link className="text-link" href="/library">Open Library <ArrowRight size={14} /></Link>}>
              {resource.data.papers.items.length === 0 ? <EmptyState title="No active papers" description="Add and scan PDFs in Streamlit; active papers will appear here." /> : (
                <DataTableShell label="Recent active papers">
                  <table><thead><tr><th>Paper</th><th>Year</th><th>Status</th></tr></thead><tbody>
                    {resource.data.papers.items.map((paper) => <tr key={paper.paper_id}><td><Link className="paper-link" href={`/papers/${encodeURIComponent(paper.paper_id)}`}>{paper.title}<small>{paper.first_author || "Author unknown"}</small></Link></td><td>{paper.year || "—"}</td><td><StatusBadge>{paper.status}</StatusBadge></td></tr>)}
                  </tbody></table>
                </DataTableShell>
              )}
            </Section>
            <Section title="Entry points">
              <div className="entry-list">
                <Link href="/library"><BookOpen size={18} /><span><strong>Open Library</strong><small>Search, browse, and manage your paper collection.</small></span><ArrowRight size={15} /></Link>
                <Link href="/library"><LibraryBig size={18} /><span><strong>Check library integrity</strong><small>Review missing files, duplicates, and recovery state.</small></span><ArrowRight size={15} /></Link>
              </div>
            </Section>
          </div>
        </>
      ) : null}
    </div>
  );
}
