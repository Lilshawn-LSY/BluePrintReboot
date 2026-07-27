"use client";

import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";
import type { SettingsState } from "../lib/api/types";

function stateTone(state: SettingsState | "available"): "healthy" | "warning" | "neutral" {
  if (state === "healthy" || state === "available") return "healthy";
  if (state === "warning") return "warning";
  return "neutral";
}

function displayedCount(state: SettingsState, count: number | null) {
  return state === "unavailable" || count === null
    ? <span className="muted-text">Unavailable</span>
    : <strong>{count}</strong>;
}

export function SettingsView() {
  const resource = useApiResource("settings-summary", apiClient.getSettingsSummary);
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Application status"
        title="Settings"
        description="Review a safe, read-only summary of the application, workspace, lightweight integrity checks, and backup evidence."
      />
      {resource.status === "loading" ? <LoadingState label="Loading Settings summary" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Settings read model unavailable" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <ErrorState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "success" ? (
        <>
          <Section title="Application" description={resource.data.application.summary}>
            <div className="summary-strip">
              <div><span>Product version</span><strong>{resource.data.application.product_version}</strong></div>
              <div><span>API state</span><StatusBadge tone={stateTone(resource.data.application.api_state)}>{resource.data.application.api_state}</StatusBadge></div>
              <div><span>API contract</span><strong>{resource.data.application.api_contract_version}</strong></div>
              <div><span>Section state</span><StatusBadge tone={stateTone(resource.data.application.state)}>{resource.data.application.state}</StatusBadge></div>
            </div>
          </Section>

          <Section title="Workspace" description={resource.data.workspace.summary}>
            {resource.data.workspace.state === "empty" ? (
              <EmptyState title="Workspace is empty" description="The safe API verified zero stored items across the available workspace stores." />
            ) : (
              <DataTableShell label="Workspace availability summary">
                <table>
                  <thead><tr><th>Store</th><th>State</th><th>Count</th><th>Summary</th></tr></thead>
                  <tbody>
                    {resource.data.workspace.resources.map((item) => (
                      <tr key={item.code}>
                        <td><strong>{item.label}</strong></td>
                        <td><StatusBadge tone={stateTone(item.state)}>{item.state}</StatusBadge></td>
                        <td>{displayedCount(item.state, item.count)}</td>
                        <td>{item.summary}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </DataTableShell>
            )}
          </Section>

          <Section title="Data integrity" description={resource.data.data_integrity.summary}>
            <DataTableShell label="Lightweight data integrity summary">
              <table>
                <thead><tr><th>Check</th><th>State</th><th>Count</th><th>Explanation</th><th>Next action</th></tr></thead>
                <tbody>
                  {resource.data.data_integrity.issues.map((issue) => (
                    <tr key={issue.code}>
                      <td><strong>{issue.code.replaceAll("_", " ")}</strong><small className="settings-severity">{issue.severity}</small></td>
                      <td><StatusBadge tone={stateTone(issue.state)}>{issue.state}</StatusBadge></td>
                      <td>{displayedCount(issue.state, issue.count)}</td>
                      <td>{issue.explanation}</td>
                      <td>{issue.next_action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DataTableShell>
          </Section>

          <Section title="Backup readiness" description={resource.data.backup_readiness.summary}>
            <div className="detail-panel">
              <dl className="metadata-list metadata-list--compact">
                <div><dt>State</dt><dd><StatusBadge tone={stateTone(resource.data.backup_readiness.state)}>{resource.data.backup_readiness.state}</StatusBadge></dd></div>
                <div><dt>Snapshot evidence</dt><dd>{resource.data.backup_readiness.snapshot_available === null ? "Unavailable" : resource.data.backup_readiness.snapshot_available ? "Available" : "Not found"}</dd></div>
                <div><dt>Last updated</dt><dd>{resource.data.backup_readiness.last_updated_at ?? "Unavailable"}</dd></div>
              </dl>
              <p className="deferred-note">Backup, restore, repair, and configuration actions remain in the existing Streamlit Settings workflow.</p>
            </div>
          </Section>
          <p className="purpose-copy">Only values returned by the safe summary API are shown; this page never generates sample counts or backup history.</p>
        </>
      ) : null}
    </div>
  );
}
