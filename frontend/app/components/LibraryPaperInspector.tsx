"use client";

import { BookOpen, X } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "./AsyncStates";
import { StatusBadge } from "./StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";
import { formatAuthorSummary } from "../lib/presentation";

function projectContext(count: number): string {
  if (count === 0) return "Not linked to a project";
  return `Linked to ${count} project${count === 1 ? "" : "s"}`;
}

export function LibraryPaperInspector({ paperId, onDismiss, onEnrich, enrichmentBusy, enrichmentContent }: {
  paperId: string;
  onDismiss: () => void;
  onEnrich: (paperId: string) => void;
  enrichmentBusy: boolean;
  enrichmentContent?: ReactNode;
}) {
  const resource = useApiResource(`library-inspector:${paperId}`, () => apiClient.getPaper(paperId));

  return (
    <aside className="library-paper-inspector" aria-label="Selected paper">
      {resource.status === "loading" ? <LoadingState label="Loading selected paper" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <EmptyState title="Paper not found" description="Choose another paper from the collection." /> : null}
      {resource.status === "error" ? <ErrorState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "success" ? (
        <>
          <div className="library-paper-inspector__heading">
            <p className="eyebrow">Selected paper</p>
            <button className="icon-button" type="button" onClick={onDismiss} aria-label="Close selected paper"><X size={16} /></button>
          </div>
          <h2>{resource.data.title || "Untitled paper"}</h2>
          <p className="library-paper-inspector__citation">{[formatAuthorSummary(resource.data.authors, resource.data.first_author), resource.data.journal, resource.data.year].filter(Boolean).join(" · ")}</p>
          <div className="badge-row">
            <StatusBadge>{resource.data.status}</StatusBadge>
            {resource.data.priority ? <StatusBadge tone="accent">{resource.data.priority}</StatusBadge> : null}
            {resource.data.missing_pdf ? <StatusBadge tone="danger">Missing PDF</StatusBadge> : null}
          </div>
          <div className="library-paper-inspector__actions">
            {!resource.data.missing_pdf && resource.data.relative_pdf_path ? <Link className="reader-action" href={`/papers/${encodeURIComponent(resource.data.paper_id)}/reader`}><BookOpen size={16} />Open Reader</Link> : null}
            <Link className="text-link" href={`/papers/${encodeURIComponent(resource.data.paper_id)}`}>View Paper Detail</Link>
            <button className="reader-control reader-control--secondary" type="button" disabled={enrichmentBusy} onClick={() => onEnrich(resource.data.paper_id)}>{enrichmentBusy ? "Loading…" : "Enrich metadata"}</button>
          </div>
          <section className="library-paper-inspector__section" aria-labelledby="selected-paper-abstract">
            <h3 id="selected-paper-abstract">Abstract</h3>
            <p className="library-paper-inspector__abstract">{resource.data.abstract || "No abstract yet."}</p>
          </section>
          <section className="library-paper-inspector__section" aria-labelledby="selected-paper-organization">
            <h3 id="selected-paper-organization">Organization</h3>
            <p className="library-paper-inspector__context">{projectContext(resource.data.project_links.length)}</p>
            {resource.data.tags.length ? <div className="tag-list">{resource.data.tags.map((item) => <StatusBadge key={item}>{item}</StatusBadge>)}</div> : <p className="library-paper-inspector__context">No tags yet</p>}
          </section>
          {enrichmentContent ? <section className="library-paper-inspector__section library-paper-inspector__enrichment" aria-label="Metadata enrichment">{enrichmentContent}</section> : null}
        </>
      ) : null}
    </aside>
  );
}
