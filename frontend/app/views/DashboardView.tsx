"use client";

import { ArrowRight, BookOpen, FolderKanban, LibraryBig, PenLine } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";
import { formatUiDate } from "../lib/presentation";

function localDraftCount(): number {
  if (typeof window === "undefined") return 0;
  try {
    const prefix = "blueprint-reboot:draft:v1:";
    let count = 0;
    for (let index = 0; index < window.localStorage.length; index += 1) {
      if ((window.localStorage.key(index) || "").startsWith(prefix)) count += 1;
    }
    return count;
  } catch {
    return 0;
  }
}

export function DashboardView() {
  const resource = useApiResource("dashboard", apiClient.getDashboard);
  const [draftCount, setDraftCount] = useState(0);
  useEffect(() => {
    const timer = window.setTimeout(() => setDraftCount(localDraftCount()), 0);
    return () => window.clearTimeout(timer);
  }, []);
  const continueReading = useMemo(() => resource.status === "success"
    ? resource.data.papers.items
    : [], [resource]);
  const activeProjects = useMemo(() => resource.status === "success"
    ? resource.data.projects.filter((project) => project.status === "active" || project.status === "paused").sort((left, right) => right.updated_at.localeCompare(left.updated_at)).slice(0, 5)
    : [], [resource]);
  const needsAttention = resource.status === "success" && (
    resource.data.library.missing_count > 0
    || resource.data.library.duplicate_count > 0
    || resource.data.library.quarantine_count > 0
    || resource.data.health.overall_state !== "healthy"
  );

  return (
    <div className="page-stack page-stack--dashboard">
      <PageHeader title="Dashboard" description="Pick up the research work that is already in motion." />
      {resource.status === "loading" ? <LoadingState label="Loading workspace overview" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "error" || resource.status === "not-found" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? <>
        <Section title="Continue reading" actions={<Link className="text-link" href="/library">Open Library <ArrowRight size={14} /></Link>}>
          {continueReading.length === 0 ? <div className="dashboard-empty-state"><EmptyState title="No papers marked Reading" description="Mark a paper as Reading in the Reader when you want it to appear here." /></div> : <DataTableShell label="Papers to continue reading"><table><thead><tr><th>Paper</th><th>Reading</th><th /></tr></thead><tbody>{continueReading.map((paper) => <tr key={paper.paper_id}><td><Link className="paper-link" href={`/papers/${encodeURIComponent(paper.paper_id)}/reader`}>{paper.title}<small>{paper.first_author || "Author unknown"}{paper.year ? ` · ${paper.year}` : ""}</small></Link></td><td><StatusBadge>{paper.status}</StatusBadge></td><td>{!paper.missing_pdf ? <Link className="text-link" href={`/papers/${encodeURIComponent(paper.paper_id)}/reader`}>Read</Link> : <StatusBadge tone="rose">Missing PDF</StatusBadge>}</td></tr>)}</tbody></table></DataTableShell>}
        </Section>
        <div className="split-layout">
          <Section title="Active projects" actions={<Link className="text-link" href="/projects">View projects <ArrowRight size={14} /></Link>}>
            {activeProjects.length === 0 ? <EmptyState title="No active projects" description="Create a project when a group of papers or notes needs a shared home." /> : <div className="dashboard-project-list">{activeProjects.map((project) => <Link key={project.project_id} href={`/projects/${encodeURIComponent(project.project_id)}`}><FolderKanban size={18} /><span><strong>{project.name}</strong><small>{project.linked_paper_count} linked paper{project.linked_paper_count === 1 ? "" : "s"} · Updated {formatUiDate(project.updated_at)}</small></span><StatusBadge>{project.status}</StatusBadge></Link>)}</div>}
          </Section>
          {draftCount ? <Section title="Drafts to continue"><Link className="dashboard-draft-card" href="/library"><PenLine size={18} /><span><strong>{draftCount} locally preserved draft{draftCount === 1 ? "" : "s"}</strong><small>Open the related Paper or Project to continue and explicitly save when ready.</small></span><ArrowRight size={15} /></Link></Section> : <Section title="Recent library activity"><div className="entry-list"><Link href="/library"><BookOpen size={18} /><span><strong>Browse your library</strong><small>Search papers, inspect context, and open the Reader.</small></span><ArrowRight size={15} /></Link></div></Section>}
        </div>
        {needsAttention ? <Section title="Needs attention"><div className="library-attention"><div><strong>Library maintenance needs a review</strong><p>{resource.data.library.missing_count ? `${resource.data.library.missing_count} missing PDF${resource.data.library.missing_count === 1 ? "" : "s"}. ` : ""}{resource.data.library.duplicate_count ? `${resource.data.library.duplicate_count} duplicate${resource.data.library.duplicate_count === 1 ? "" : "s"}. ` : ""}{resource.data.library.quarantine_count ? `${resource.data.library.quarantine_count} quarantined item${resource.data.library.quarantine_count === 1 ? "" : "s"}.` : ""}</p></div><Link className="text-link" href="/settings/diagnostics"><LibraryBig size={15} />Open Diagnostics</Link></div></Section> : null}
      </> : null}
    </div>
  );
}
