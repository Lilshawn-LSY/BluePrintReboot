"use client";

import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { DetailPanel } from "../components/DetailPanel";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";

export function LibraryView() {
  const resource = useApiResource("library", async () => {
    const [health, status] = await Promise.all([apiClient.getHealth(), apiClient.getLibraryStatus()]);
    return { health, status };
  });
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Files and integrity" title="Library" description="Monitor PDF lifecycle, missing files, duplicates, quarantine, and recovery readiness. Reading workflows live under Papers." />
      {resource.status === "loading" ? <LoadingState label="Reading library status" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "error" || resource.status === "not-found" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? (
        <>
          <Section title="Integrity summary" description="Current read-only health indicators; maintenance actions remain in Streamlit.">
            <div className="summary-strip summary-strip--six">
              <div><span>Overall</span><StatusBadge tone={resource.data.health.overall_state === "healthy" ? "healthy" : "warning"}>{resource.data.health.overall_state}</StatusBadge></div>
              <div><span>Missing PDFs</span><strong>{resource.data.status.missing_count}</strong></div>
              <div><span>Duplicates</span><strong>{resource.data.status.duplicate_count}</strong></div>
              <div><span>Corrupt state</span><strong>{resource.data.status.corrupt_count}</strong></div>
              <div><span>Quarantine</span><strong>{resource.data.status.quarantine_count}</strong></div>
              <div><span>Archived</span><strong>{resource.data.status.archived_count}</strong></div>
            </div>
          </Section>
          <Section title="Workspace warnings" description="Stable, non-sensitive guidance supplied by the API.">
            {resource.data.status.workspace_warnings.length === 0 ? <EmptyState title="No workspace warnings" description="The current library status does not report a maintenance warning." /> : <ul className="warning-list">{resource.data.status.workspace_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
          </Section>
          <DetailPanel title="Maintenance availability"><p>PDF ingestion, duplicate decisions, archive changes, repair, quarantine, restore, and backup remain available only in the primary Streamlit interface for this release.</p></DetailPanel>
        </>
      ) : null}
    </div>
  );
}
