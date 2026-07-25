"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { DetailPanel } from "../components/DetailPanel";
import { PageHeader } from "../components/PageHeader";
import { PdfJsReader } from "../components/PdfJsReader";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { apiClient } from "../lib/api/client";
import type { PaperDetail } from "../lib/api/types";


function ReaderPdf({ paper }: { paper: PaperDetail }) {
  if (paper.missing_pdf || !paper.relative_pdf_path) {
    return <EmptyState title="Managed PDF missing" description="This paper record does not currently have an accessible PDF in the managed library." />;
  }
  return <PdfJsReader paperId={paper.paper_id} />;
}


export function ReaderView({ paperId }: { paperId: string }) {
  const [retryCount, setRetryCount] = useState(0);
  const resource = useApiResource(`reader-paper:${paperId}:${retryCount}`, () => apiClient.getPaper(paperId));
  const detailHref = `/papers/${encodeURIComponent(paperId)}`;
  return (
    <div className="page-stack">
      <Link className="back-link" href={detailHref}><ArrowLeft size={15} />Back to Paper Detail</Link>
      {resource.status === "loading" ? <LoadingState label="Loading paper metadata" /> : null}
      {resource.status === "unavailable" ? (
        <div className="reader-metadata-state">
          <UnavailableState description={resource.message} />
          <button className="reader-control" type="button" onClick={() => setRetryCount((value) => value + 1)}>Retry local API</button>
        </div>
      ) : null}
      {resource.status === "not-found" ? <EmptyState title="Paper not found" description="The requested paper identity is not present in the local read model." /> : null}
      {resource.status === "error" ? (
        <div className="reader-metadata-state">
          <ErrorState description={resource.message} />
          <button className="reader-control" type="button" onClick={() => setRetryCount((value) => value + 1)}>Retry local API</button>
        </div>
      ) : null}
      {resource.status === "success" ? (
        <>
          <PageHeader
            eyebrow="Read-only Reader"
            title={resource.data.title}
            description={[resource.data.authors.join(", ") || "Authors unknown", resource.data.journal, resource.data.year].filter(Boolean).join(" · ") || "Citation metadata is incomplete."}
            actions={<StatusBadge tone={resource.data.archived ? "neutral" : "accent"}>{resource.data.lifecycle_state}</StatusBadge>}
          />
          <div className="reader-layout">
            <section className="reader-stage" aria-label="Managed PDF viewing region">
              <ReaderPdf paper={resource.data} />
            </section>
            <DetailPanel title="Read-only context">
              <dl className="metadata-list metadata-list--compact">
                <div><dt>First author</dt><dd>{resource.data.first_author || "Unknown"}</dd></div>
                <div><dt>Year</dt><dd>{resource.data.year || "Unknown"}</dd></div>
                <div><dt>Journal</dt><dd>{resource.data.journal || "Unknown"}</dd></div>
                <div><dt>Status</dt><dd>{resource.data.status}</dd></div>
              </dl>
              <p className="deferred-note">Notes, metadata changes, and every write action remain in Streamlit. This web Reader is read-only.</p>
            </DetailPanel>
          </div>
        </>
      ) : null}
    </div>
  );
}
