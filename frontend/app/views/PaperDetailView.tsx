"use client";

import { BookOpen, LibraryBig } from "lucide-react";
import Link from "next/link";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { DetailPanel } from "../components/DetailPanel";
import { FirstPageThumbnail } from "../components/FirstPageThumbnail";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";
import { abstractDisplayParagraphs } from "../lib/abstract-display.mjs";
import { formatAuthorSummary } from "../lib/presentation";

function projectContext(count: number): string {
  if (count === 0) return "This Paper is not linked to a Project yet.";
  return `This Paper is linked to ${count} Project${count === 1 ? "" : "s"}.`;
}

export function PaperDetailView({ paperId }: { paperId: string }) {
  const resource = useApiResource(`paper:${paperId}`, () => apiClient.getPaper(paperId));
  const abstractParagraphs = resource.status === "success"
    ? abstractDisplayParagraphs(resource.data.abstract)
    : [];
  return (
    <div className="page-stack page-stack--detail paper-detail-overview">
      {resource.status === "loading" ? <LoadingState label="Loading paper" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "not-found" ? <EmptyState title="Paper not found" description="Return to the Library to choose a paper." /> : null}
      {resource.status === "error" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? (
        <>
          <Breadcrumbs items={[{ label: "Library", href: "/library" }, { label: resource.data.title || "Paper" }]} />
          <PageHeader title={resource.data.title || "Untitled paper"} description={[formatAuthorSummary(resource.data.authors, resource.data.first_author), resource.data.journal, resource.data.year].filter(Boolean).join(" · ")} actions={<div className="paper-detail-actions"><div className="badge-row"><StatusBadge>{resource.data.status}</StatusBadge>{resource.data.priority ? <StatusBadge>{resource.data.priority}</StatusBadge> : null}{resource.data.archived ? <StatusBadge>Archived</StatusBadge> : null}{resource.data.missing_pdf ? <StatusBadge tone="rose">Missing PDF</StatusBadge> : null}</div>{!resource.data.missing_pdf && resource.data.relative_pdf_path ? <Link className="reader-action" href={`/papers/${encodeURIComponent(resource.data.paper_id)}/reader`}><BookOpen size={16} />Open Reader</Link> : <div className="paper-detail-recovery"><span className="reader-action reader-action--disabled" aria-disabled="true">Reader unavailable</span><Link className="reader-action" href="/library"><LibraryBig size={16} />Reconnect PDF</Link><Link className="text-link" href="/settings/diagnostics">Review diagnostics</Link></div>}</div>} />
          <dl className="paper-dossier-summary" aria-label="Paper reading context">
            <div><dt>PDF</dt><dd>{resource.data.missing_pdf ? <StatusBadge tone="rose">Missing PDF</StatusBadge> : "Available in Reader"}</dd></div>
            <div><dt>Reading</dt><dd><StatusBadge>{resource.data.status}</StatusBadge></dd></div>
            <div><dt>Notes</dt><dd>{resource.data.note_available ? "Reading Note available" : "Ready to begin"}</dd></div>
          </dl>
          <div className="paper-detail-content-grid">
            <div className="paper-detail-main">
              <Section title="Abstract">
                {abstractParagraphs.length ? <div className="abstract-text paper-detail-abstract">{abstractParagraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div> : <p className="abstract-text paper-detail-abstract">No abstract yet.</p>}
              </Section>
              <Section title="Canonical Tags">
                {resource.data.tags.length ? <div className="tag-list">{resource.data.tags.map((tag) => <StatusBadge presentation="chip" taxonomy="canonical" key={tag}>{tag}</StatusBadge>)}</div> : <p className="deferred-note">No canonical Tags are linked to this Paper.</p>}
              </Section>
              <Section title="Linked research">
                <div className="paper-linked-research"><p>{projectContext(resource.data.project_links.length)}</p><Link className="text-link" href="/projects">Open Projects <span aria-hidden="true">→</span></Link></div>
              </Section>
            </div>
            <aside className="paper-detail-context" aria-label="Paper context">
              <FirstPageThumbnail paperId={resource.data.paper_id} available={!resource.data.missing_pdf && Boolean(resource.data.relative_pdf_path)} size="detail" />
              <DetailPanel title="Next step"><p>{resource.data.missing_pdf ? "Reconnect the managed PDF before opening Reader." : resource.data.note_available ? "Continue the Reading Note in Reader." : "Open Reader and begin recording your response."}</p></DetailPanel>
            </aside>
          </div>
          {resource.data.keywords.length ? <Section title="Imported keywords"><div className="tag-list">{resource.data.keywords.map((keyword) => <StatusBadge presentation="chip" taxonomy="alias" key={keyword}>{keyword}</StatusBadge>)}</div></Section> : null}
          <details className="paper-dossier-maintenance">
            <summary>Citation and metadata review</summary>
            <dl className="metadata-list paper-citation">
              <div><dt>Authors</dt><dd>{resource.data.authors.join("; ") || "Authors unknown"}</dd></div>
              <div><dt>Journal</dt><dd>{resource.data.journal || "Not recorded"}</dd></div>
              <div><dt>Year</dt><dd>{resource.data.year || "Not recorded"}</dd></div>
              <div><dt>DOI</dt><dd className="paper-identifier">{resource.data.doi || "Not recorded"}</dd></div>
              <div><dt>arXiv</dt><dd className="paper-identifier">{resource.data.arxiv_id || "Not recorded"}</dd></div>
            </dl>
            <Link className="text-link paper-dossier-maintenance__action" href={`/papers/${encodeURIComponent(resource.data.paper_id)}/reader`}>Review metadata in Reader</Link>
          </details>
        </>
      ) : null}
    </div>
  );
}
