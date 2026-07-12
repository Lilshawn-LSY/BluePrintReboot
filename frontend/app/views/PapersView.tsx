"use client";

import Link from "next/link";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { SearchInput } from "../components/SearchInput";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { Toolbar } from "../components/Toolbar";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";

export function PapersView() {
  const resource = useApiResource("papers-active", () => apiClient.getPapers({ limit: 100, archiveStatus: "active" }));
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Reading collection" title="Papers" description="Browse the active paper collection and open stable citation metadata. Search and richer reading tools arrive in later releases." />
      <Toolbar label="Paper collection tools"><SearchInput disabled placeholder="Search coming later" /><span className="toolbar-note">Active papers · deterministic title order</span></Toolbar>
      {resource.status === "loading" ? <LoadingState label="Loading papers" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "error" || resource.status === "not-found" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? (
        <Section title="Active papers" description={`${resource.data.total} paper${resource.data.total === 1 ? "" : "s"} in the current collection.`}>
          {resource.data.items.length === 0 ? <EmptyState title="No active papers" description="Add and scan PDFs in Streamlit; this view never substitutes fake paper data." /> : (
            <DataTableShell label="Active paper collection">
              <table><thead><tr><th>Title</th><th>Author</th><th>Year</th><th>Status</th><th>Priority</th><th>File</th></tr></thead><tbody>
                {resource.data.items.map((paper) => (
                  <tr key={paper.paper_id}>
                    <td><Link className="paper-link" href={`/papers/${encodeURIComponent(paper.paper_id)}`}>{paper.title}<small className="mono-id">{paper.paper_id}</small></Link></td>
                    <td>{paper.first_author || "—"}</td><td>{paper.year || "—"}</td><td><StatusBadge>{paper.status}</StatusBadge></td><td>{paper.priority}</td><td>{paper.missing_pdf ? <StatusBadge tone="danger">Missing PDF</StatusBadge> : <StatusBadge tone="healthy">Available</StatusBadge>}</td>
                  </tr>
                ))}
              </tbody></table>
            </DataTableShell>
          )}
        </Section>
      ) : null}
    </div>
  );
}
