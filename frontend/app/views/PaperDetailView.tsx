"use client";

import { ArrowLeft, BookOpen } from "lucide-react";
import Link from "next/link";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { DetailPanel } from "../components/DetailPanel";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";

export function PaperDetailView({ paperId }: { paperId: string }) {
  const resource = useApiResource(`paper:${paperId}`, () => apiClient.getPaper(paperId));
  return (
    <div className="page-stack">
      <Link className="back-link" href="/papers"><ArrowLeft size={15} />Back to papers</Link>
      {resource.status === "loading" ? <LoadingState label="Loading paper detail" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "not-found" ? <EmptyState title="Paper not found" description="The requested paper identity is not present in the local read model." /> : null}
      {resource.status === "error" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? (
        <>
          <PageHeader eyebrow="Paper detail" title={resource.data.title} description={[resource.data.authors.join(", ") || "Authors unknown", resource.data.journal, resource.data.year].filter(Boolean).join(" · ") || "Citation metadata is incomplete."} actions={<div className="paper-detail-actions"><div className="badge-row"><StatusBadge tone={resource.data.archived ? "neutral" : "accent"}>{resource.data.lifecycle_state}</StatusBadge><StatusBadge>{resource.data.status}</StatusBadge>{resource.data.missing_pdf ? <StatusBadge tone="danger">Missing PDF</StatusBadge> : null}</div>{!resource.data.missing_pdf && resource.data.relative_pdf_path ? <Link className="reader-action" href={`/papers/${encodeURIComponent(resource.data.paper_id)}/reader`}><BookOpen size={16} />Open Reader</Link> : <span className="reader-action reader-action--disabled" aria-disabled="true">Reader unavailable</span>}</div>} />
          <div className="detail-grid">
            <Section title="Citation metadata" description="Stored metadata from the stable read-only paper contract.">
              <dl className="metadata-list">
                <div><dt>Authors</dt><dd>{resource.data.authors.join("; ") || "—"}</dd></div>
                <div><dt>Journal</dt><dd>{resource.data.journal || "—"}</dd></div>
                <div><dt>Year</dt><dd>{resource.data.year || "—"}</dd></div>
                <div><dt>DOI</dt><dd className="mono-id">{resource.data.doi || "—"}</dd></div>
                <div><dt>arXiv</dt><dd className="mono-id">{resource.data.arxiv_id || "—"}</dd></div>
                <div><dt>Priority</dt><dd>{resource.data.priority}</dd></div>
              </dl>
            </Section>
            <DetailPanel title="Reading context">
              <dl className="metadata-list metadata-list--compact">
                <div><dt>Note</dt><dd>{resource.data.note_available ? "Available" : "Not created"}</dd></div>
                <div><dt>Extracted text</dt><dd>{resource.data.extracted_text_available ? "Available" : "Unavailable"}</dd></div>
                <div><dt>Profile</dt><dd>{resource.data.profile_available ? "Available" : "Unavailable"}</dd></div>
                <div><dt>Projects</dt><dd>{resource.data.project_links.length}</dd></div>
              </dl>
              <p className="deferred-note">Notes, metadata changes, and all write actions remain in Streamlit in v1.3.0.</p>
            </DetailPanel>
          </div>
          <Section title="Abstract"><div className="abstract-text">{resource.data.abstract || <span className="muted-text">No abstract is stored for this paper.</span>}</div></Section>
          <Section title="Tags and keywords"><div className="tag-list">{[...resource.data.tags, ...resource.data.keywords].length ? [...resource.data.tags, ...resource.data.keywords].map((item, index) => <StatusBadge key={`${item}-${index}`}>{item}</StatusBadge>) : <span className="muted-text">No tags or keywords are stored.</span>}</div></Section>
        </>
      ) : null}
    </div>
  );
}
