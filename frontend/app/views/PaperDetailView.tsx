"use client";

import { BookOpen } from "lucide-react";
import Link from "next/link";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { DetailPanel } from "../components/DetailPanel";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";
import { abstractDisplayParagraphs } from "../lib/abstract-display.mjs";
import { formatAuthorSummary } from "../lib/presentation";

function projectContext(count: number): string {
  if (count === 0) return "No linked projects";
  return `Linked to ${count} project${count === 1 ? "" : "s"}`;
}

export function PaperDetailView({ paperId }: { paperId: string }) {
  const resource = useApiResource(`paper:${paperId}`, () => apiClient.getPaper(paperId));
  return (
    <div className="page-stack paper-detail-overview">
      {resource.status === "loading" ? <LoadingState label="Loading paper" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "not-found" ? <EmptyState title="Paper not found" description="Return to the Library to choose a paper." /> : null}
      {resource.status === "error" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? (
        <>
          <Breadcrumbs items={[{ label: "Library", href: "/library" }, { label: resource.data.title || "Paper" }]} />
          <PageHeader title={resource.data.title || "Untitled paper"} description={[formatAuthorSummary(resource.data.authors, resource.data.first_author), resource.data.journal, resource.data.year].filter(Boolean).join(" · ")} actions={<div className="paper-detail-actions"><div className="badge-row"><StatusBadge>{resource.data.status}</StatusBadge>{resource.data.priority ? <StatusBadge tone="accent">{resource.data.priority}</StatusBadge> : null}{resource.data.archived ? <StatusBadge>Archived</StatusBadge> : null}{resource.data.missing_pdf ? <StatusBadge tone="danger">Missing PDF</StatusBadge> : null}</div>{!resource.data.missing_pdf && resource.data.relative_pdf_path ? <Link className="reader-action" href={`/papers/${encodeURIComponent(resource.data.paper_id)}/reader`}><BookOpen size={16} />Open Reader</Link> : <span className="reader-action reader-action--disabled" aria-disabled="true">Reader unavailable</span>}</div>} />
          <div className="paper-detail-content-grid">
            <div className="paper-detail-main">
              <Section title="Abstract">
                {resource.data.abstract ? <div className="abstract-text paper-detail-abstract">{abstractDisplayParagraphs(resource.data.abstract).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div> : <p className="abstract-text paper-detail-abstract">No abstract yet.</p>}
              </Section>
              <Section title="Citation">
                <dl className="metadata-list paper-citation">
                  <div><dt>Authors</dt><dd>{resource.data.authors.join("; ") || "Authors unknown"}</dd></div>
                  <div><dt>Journal</dt><dd>{resource.data.journal || "Not recorded"}</dd></div>
                  <div><dt>Year</dt><dd>{resource.data.year || "Not recorded"}</dd></div>
                  <div><dt>DOI</dt><dd className="paper-identifier">{resource.data.doi || "Not recorded"}</dd></div>
                  <div><dt>arXiv</dt><dd className="paper-identifier">{resource.data.arxiv_id || "Not recorded"}</dd></div>
                </dl>
              </Section>
            </div>
            <aside className="paper-detail-context" aria-label="Paper context">
              <DetailPanel title="Organization"><p>{projectContext(resource.data.project_links.length)}</p>{resource.data.tags.length ? <div className="tag-list project-tag-row">{resource.data.tags.map((tag) => <StatusBadge key={tag}>{tag}</StatusBadge>)}</div> : <p className="deferred-note">No tags yet</p>}</DetailPanel>
              <DetailPanel title="Reading context"><p>{resource.data.note_available ? "A reading note is ready in Reader." : "Open Reader to begin a reading note."}</p></DetailPanel>
            </aside>
          </div>
          {resource.data.keywords.length ? <Section title="Keywords"><div className="tag-list">{resource.data.keywords.map((keyword) => <StatusBadge key={keyword}>{keyword}</StatusBadge>)}</div></Section> : null}
        </>
      ) : null}
    </div>
  );
}
