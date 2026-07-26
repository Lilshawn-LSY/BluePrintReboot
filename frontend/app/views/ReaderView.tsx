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
import type { ReaderSnapshot } from "../lib/api/types";


function ReaderPdf({ snapshot }: { snapshot: ReaderSnapshot }) {
  if (snapshot.pdf_state === "missing" || snapshot.paper.missing_pdf || !snapshot.paper.relative_pdf_path) {
    return (
      <EmptyState
        title="Managed PDF missing"
        description={snapshot.unavailable_reason || "This paper record does not currently have an accessible PDF in the managed library."}
      />
    );
  }
  return <PdfJsReader paperId={snapshot.paper.paper_id} />;
}


function SavedNoteCompanion({ snapshot }: { snapshot: ReaderSnapshot }) {
  const noteUnavailable = snapshot.warnings.includes("saved_note_unavailable");
  return (
    <section className="reader-note" aria-labelledby="saved-reading-note-title">
      <div className="reader-note__heading">
        <div>
          <p className="eyebrow">Persisted companion</p>
          <h2 id="saved-reading-note-title">Saved Reading Note</h2>
        </div>
        <StatusBadge tone={noteUnavailable ? "warning" : snapshot.saved_note_available ? "accent" : "neutral"}>
          {noteUnavailable ? "Unavailable" : snapshot.saved_note_available ? "Saved" : "Empty"}
        </StatusBadge>
      </div>
      {noteUnavailable ? (
        <div className="reader-note__message" role="status">
          The persisted note could not be read. The PDF remains available independently.
        </div>
      ) : snapshot.saved_note_available ? (
        <pre className="reader-note__content" tabIndex={0}>{snapshot.saved_note_content}</pre>
      ) : (
        <div className="reader-note__message">No persisted Reading Note exists for this paper.</div>
      )}
      <p className="deferred-note">This companion is plain-text and read-only. Note editing and every write action remain in Streamlit.</p>
    </section>
  );
}


export function ReaderView({ paperId }: { paperId: string }) {
  const [retryCount, setRetryCount] = useState(0);
  const resource = useApiResource(
    `reader-snapshot:${paperId}:${retryCount}`,
    () => apiClient.getReaderSnapshot(paperId),
  );
  const detailHref = `/papers/${encodeURIComponent(paperId)}`;
  return (
    <div className="page-stack">
      <Link className="back-link" href={detailHref}><ArrowLeft size={15} />Back to Paper Detail</Link>
      {resource.status === "loading" ? <LoadingState label="Loading Reader snapshot" /> : null}
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
            title={resource.data.paper.title}
            description={[
              resource.data.paper.authors.join(", ") || "Authors unknown",
              resource.data.paper.journal,
              resource.data.paper.year,
            ].filter(Boolean).join(" · ") || "Citation metadata is incomplete."}
            actions={<StatusBadge tone={resource.data.paper.archived ? "neutral" : "accent"}>{resource.data.paper.lifecycle_state}</StatusBadge>}
          />
          <div className="reader-layout">
            <section className="reader-stage" aria-label="Managed PDF viewing region">
              <ReaderPdf snapshot={resource.data} />
            </section>
            <aside className="reader-companion" aria-label="Read-only Reader companion">
              <SavedNoteCompanion snapshot={resource.data} />
              <DetailPanel title="Read-only context">
                <dl className="metadata-list metadata-list--compact">
                  <div><dt>First author</dt><dd>{resource.data.paper.first_author || "Unknown"}</dd></div>
                  <div><dt>Year</dt><dd>{resource.data.paper.year || "Unknown"}</dd></div>
                  <div><dt>Journal</dt><dd>{resource.data.paper.journal || "Unknown"}</dd></div>
                  <div><dt>Status</dt><dd>{resource.data.paper.status}</dd></div>
                </dl>
              </DetailPanel>
            </aside>
          </div>
        </>
      ) : null}
    </div>
  );
}
