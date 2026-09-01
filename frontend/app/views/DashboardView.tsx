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
      <PageHeader title="Dashboard" description="Resume a paper, a draft, or a project that already has momentum." />
      {resource.status === "loading" ? <LoadingState label="Loading workspace overview" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "error" || resource.status === "not-found" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? <>
        <Section title="Resume research" actions={<Link className="text-link" href="/library">Find a Paper <ArrowRight size={14} /></Link>}>
          {continueReading.length === 0 ? <div className="dashboard-empty-state"><EmptyState title="Nothing is queued for reading" description="Open a Paper from the Library and mark it Reading when you want it to return here." /></div> : <DataTableShell label="Papers ready to resume"><table className="dashboard-resume-queue"><thead><tr><th>Paper</th><th>Reading state</th><th><span className="sr-only">Next action</span></th></tr></thead><tbody>{continueReading.map((paper) => <tr key={paper.paper_id}><td><Link className="paper-link" href={`/papers/${encodeURIComponent(paper.paper_id)}/reader`}>{paper.title}<small>{paper.first_author || "Author unknown"}{paper.year ? ` · ${paper.year}` : ""}</small></Link></td><td><StatusBadge>{paper.status}</StatusBadge></td><td>{!paper.missing_pdf ? <Link className="dashboard-action-link" href={`/papers/${encodeURIComponent(paper.paper_id)}/reader`}>Continue reading <ArrowRight size={14} /></Link> : <Link className="dashboard-action-link dashboard-action-link--attention" href="/library">Reconnect PDF <ArrowRight size={14} /></Link>}</td></tr>)}</tbody></table></DataTableShell>}
        </Section>
        <div className="split-layout">
          <Section title="Recent Projects" actions={<Link className="text-link" href="/projects">View all Projects <ArrowRight size={14} /></Link>}>
            {activeProjects.length === 0 ? <EmptyState title="No active Projects" description="Create a Project when a group of papers or notes needs a shared research question." /> : <div className="dashboard-project-list">{activeProjects.map((project) => <Link key={project.project_id} href={`/projects/${encodeURIComponent(project.project_id)}`}><FolderKanban size={18} /><span><strong>{project.name}</strong><small>{project.linked_paper_count} linked paper{project.linked_paper_count === 1 ? "" : "s"} · Updated {formatUiDate(project.updated_at)}</small></span><span className="dashboard-row-action">Open Project <ArrowRight size={14} /></span></Link>)}</div>}
          </Section>
          {draftCount ? <Section title="Resume a draft"><Link className="dashboard-draft-card" href="/library"><PenLine size={18} /><span><strong>{draftCount} locally preserved draft{draftCount === 1 ? "" : "s"}</strong><small>Open its Paper or Project, review the draft, then explicitly save when ready.</small></span><span className="dashboard-row-action">Resume draft <ArrowRight size={15} /></span></Link></Section> : <Section title="Start the next pass"><div className="entry-list"><Link href="/library"><BookOpen size={18} /><span><strong>Choose a Paper from the Library</strong><small>Search, filter, inspect the context, then open the Reader.</small></span><span className="dashboard-row-action">Open Library <ArrowRight size={15} /></span></Link></div></Section>}
        </div>
        {needsAttention ? <Section title="Action required"><div className="library-attention"><div><strong>Research material needs a safe review</strong><p>{resource.data.library.missing_count ? `${resource.data.library.missing_count} missing PDF${resource.data.library.missing_count === 1 ? "" : "s"}. ` : ""}{resource.data.library.duplicate_count ? `${resource.data.library.duplicate_count} duplicate${resource.data.library.duplicate_count === 1 ? "" : "s"}. ` : ""}{resource.data.library.quarantine_count ? `${resource.data.library.quarantine_count} quarantined item${resource.data.library.quarantine_count === 1 ? "" : "s"}.` : ""}</p></div><Link className="text-link" href="/settings/diagnostics"><LibraryBig size={15} />Review Diagnostics</Link></div></Section> : null}
      </> : null}
    </div>
  );
}
