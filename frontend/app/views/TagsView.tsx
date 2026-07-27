"use client";

import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";

export function TagsView() {
  const resource = useApiResource("tags", async () => {
    const [tags, summary] = await Promise.all([
      apiClient.getTags({ limit: 100 }),
      apiClient.getTagSummary(),
    ]);
    return { tags, summary };
  });
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Knowledge organization" title="Tags" description="Review the canonical Tag Book vocabulary and a counts-only summary derived from existing local candidate evidence." />
      {resource.status === "loading" ? <LoadingState label="Loading canonical Tags" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Tag Book read model unavailable" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <ErrorState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "success" ? (
        <>
          <Section title="Candidate summary" description="Counts only; no candidates or quality statistics are invented when the source is absent.">
            {resource.data.summary.availability === "unavailable" ? (
              <EmptyState title="Candidate summary unavailable" description="No readable persisted paper-index source is available for deterministic candidate evidence." />
            ) : resource.data.summary.state === "empty" ? (
              <EmptyState title="No candidate evidence" description={`The real source was evaluated across ${resource.data.summary.evaluated_paper_count} paper records and produced no candidates.`} />
            ) : (
              <div className="summary-strip summary-strip--six">
                <div><span>Candidates</span><strong>{resource.data.summary.candidate_count}</strong></div>
                <div><span>Known matches</span><strong>{resource.data.summary.known_canonical_match_count}</strong></div>
                <div><span>High</span><strong>{resource.data.summary.quality_counts.high}</strong></div>
                <div><span>Medium</span><strong>{resource.data.summary.quality_counts.medium}</strong></div>
                <div><span>Weak</span><strong>{resource.data.summary.quality_counts.weak}</strong></div>
                <div><span>Rejected</span><strong>{resource.data.summary.quality_counts.rejected}</strong></div>
              </div>
            )}
          </Section>
          <Section title="Canonical Tags" description={`${resource.data.tags.total} canonical Tag${resource.data.tags.total === 1 ? "" : "s"} from the ${resource.data.tags.source_state === "legacy_fallback" ? "legacy fallback" : "primary Tag Book"}.`}>
            {resource.data.tags.items.length === 0 ? (
              <EmptyState title="Tag Book is empty" description="No canonical Tags are stored. This view never supplies generated examples." />
            ) : (
              <DataTableShell label="Canonical Tag Book">
                <table>
                  <thead><tr><th>Label</th><th>Canonical key</th><th>Category</th><th>Aliases</th><th>Status</th><th>Strength</th></tr></thead>
                  <tbody>
                    {resource.data.tags.items.map((tag) => (
                      <tr key={tag.canonical_key}>
                        <td><strong>{tag.label}</strong></td>
                        <td className="mono-id">{tag.canonical_key}</td>
                        <td>{tag.category}</td>
                        <td>
                          <div className="tag-list">
                            {tag.aliases.length
                              ? tag.aliases.map((alias) => <StatusBadge key={alias}>{alias}</StatusBadge>)
                              : <span className="muted-text">None stored</span>}
                          </div>
                        </td>
                        <td><StatusBadge tone={tag.status === "active" ? "healthy" : "warning"}>{tag.status}</StatusBadge></td>
                        <td>{tag.suggestion_strength}</td>
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
