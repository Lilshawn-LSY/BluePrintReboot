"use client";

import Link from "next/link";
import { useState } from "react";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { DataTableShell } from "../components/DataTableShell";
import { LibraryPaperInspector } from "../components/LibraryPaperInspector";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { Toolbar } from "../components/Toolbar";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";
import type { EditablePaperMetadata, ManagedPdfImportResponse, ManagedPdfScanResponse, MetadataEnrichmentPreview } from "../lib/api/types";

const PAGE_SIZE = 20;
const FIELD_LABELS: Record<keyof EditablePaperMetadata, string> = {
  title: "Title", authors: "Authors", year: "Year", journal: "Journal", doi: "DOI", abstract: "Abstract", keywords: "Keywords",
};

function scanTone(status: string): "healthy" | "warning" | "danger" | "neutral" {
  if (status === "new" || status === "imported" || status === "reconnected") return "healthy";
  if (["already_registered", "duplicate_content", "reconnect_available", "reconnect_ambiguous"].includes(status)) return "warning";
  if (["invalid", "unavailable", "missing"].includes(status)) return "danger";
  return "neutral";
}

function friendlyCommandError(error: unknown): string {
  return error instanceof ApiClientError ? error.message : "The PDF action could not be completed.";
}

function libraryNeedsAttention(data: { health: { overall_state: string }; status: { degraded: boolean; missing_count: number; duplicate_count: number; quarantine_count: number; workspace_warnings: string[] } }): boolean {
  return data.health.overall_state !== "healthy" || data.status.degraded || data.status.missing_count > 0 || data.status.duplicate_count > 0 || data.status.quarantine_count > 0 || data.status.workspace_warnings.length > 0;
}

export function LibraryView() {
  const resource = useApiResource("library", async () => {
    const [health, status] = await Promise.all([apiClient.getHealth(), apiClient.getLibraryStatus()]);
    return { health, status };
  });
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [year, setYear] = useState("");
  const [readingStatus, setReadingStatus] = useState("");
  const [archiveStatus, setArchiveStatus] = useState<"active" | "archived" | "all">("active");
  const [offset, setOffset] = useState(0);
  const [selectedPaperId, setSelectedPaperId] = useState("");
  const [showImport, setShowImport] = useState(false);
  const collection = useApiResource(
    `library-papers:${q}:${tag}:${year}:${readingStatus}:${archiveStatus}:${offset}`,
    () => apiClient.getPapers({ limit: PAGE_SIZE, offset, archiveStatus, q, tag, year, status: readingStatus }),
  );
  const [scan, setScan] = useState<ManagedPdfScanResponse | null>(null);
  const [scanError, setScanError] = useState("");
  const [scanBusy, setScanBusy] = useState(false);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [importResult, setImportResult] = useState<ManagedPdfImportResponse | null>(null);
  const [importError, setImportError] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [reconnectBusy, setReconnectBusy] = useState("");
  const [reconnectMessage, setReconnectMessage] = useState("");
  const [enrichmentPaperId, setEnrichmentPaperId] = useState("");
  const [enrichment, setEnrichment] = useState<MetadataEnrichmentPreview | null>(null);
  const [enrichmentError, setEnrichmentError] = useState("");
  const [enrichmentBusy, setEnrichmentBusy] = useState(false);
  const [selectedFields, setSelectedFields] = useState<Array<keyof EditablePaperMetadata>>([]);

  const resetCollection = () => { setOffset(0); setSelectedPaperId(""); setEnrichmentPaperId(""); setEnrichment(null); setSelectedFields([]); };
  const selectPaper = (paperId: string) => { setSelectedPaperId(paperId); setEnrichmentPaperId(""); setEnrichment(null); setSelectedFields([]); };
  const changePage = (nextOffset: number) => { setOffset(nextOffset); setSelectedPaperId(""); setEnrichmentPaperId(""); setEnrichment(null); setSelectedFields([]); };
  const closeInspector = () => { setSelectedPaperId(""); setEnrichmentPaperId(""); setEnrichment(null); setSelectedFields([]); };
  const scanPdfs = async () => {
    setScanBusy(true); setScanError(""); setImportError(""); setImportResult(null); setReconnectMessage("");
    try { setScan(await apiClient.scanManagedPdfs()); setSelectedPaths([]); }
    catch (error) { setScan(null); setScanError(friendlyCommandError(error)); }
    finally { setScanBusy(false); }
  };
  const openImport = () => { setShowImport(true); void scanPdfs(); };
  const importSelected = async () => {
    if (!selectedPaths.length) return;
    setImportBusy(true); setImportError("");
    try { setImportResult(await apiClient.importManagedPdfs(selectedPaths)); setSelectedPaths([]); collection.retry(); resource.retry(); }
    catch (error) { setImportError(friendlyCommandError(error)); }
    finally { setImportBusy(false); }
  };
  const toggleSelection = (relativePath: string) => setSelectedPaths((current) => current.includes(relativePath)
    ? current.filter((item) => item !== relativePath)
    : [...current, relativePath]);
  const reconnect = async (paperId: string, relativePath: string) => {
    setReconnectBusy(relativePath); setReconnectMessage(""); setImportError("");
    try {
      const result = await apiClient.reconnectManagedPdf(paperId, relativePath);
      setReconnectMessage(result.message); collection.retry(); resource.retry(); await scanPdfs();
    } catch (error) { setImportError(friendlyCommandError(error)); }
    finally { setReconnectBusy(""); }
  };
  const previewEnrichment = async (paperId: string) => {
    setEnrichmentPaperId(paperId); setEnrichment(null); setSelectedFields([]); setEnrichmentError(""); setEnrichmentBusy(true);
    try { setEnrichment(await apiClient.previewMetadataEnrichment(paperId)); }
    catch (error) { setEnrichmentError(friendlyCommandError(error)); }
    finally { setEnrichmentBusy(false); }
  };
  const applyEnrichment = async () => {
    if (!enrichment || !selectedFields.length) return;
    const fields = new Map(enrichment.fields.map((field) => [field.field, field]));
    const changes = Object.fromEntries(selectedFields.map((field) => [field, fields.get(field)?.candidate_value || ""])) as Partial<EditablePaperMetadata>;
    setEnrichmentBusy(true); setEnrichmentError("");
    try {
      await apiClient.saveReaderMetadata(enrichment.paper_id, changes, enrichment.metadata_revision);
      setEnrichment(null); setSelectedFields([]); setEnrichmentPaperId(""); collection.retry();
    } catch (error) { setEnrichmentError(friendlyCommandError(error)); }
    finally { setEnrichmentBusy(false); }
  };
  const toggleField = (field: keyof EditablePaperMetadata) => setSelectedFields((current) => current.includes(field) ? current.filter((item) => item !== field) : [...current, field]);
  const attention = resource.status === "success" && libraryNeedsAttention(resource.data);

  return (
    <div className="page-stack">
      <PageHeader title="Library" actions={<button className="reader-control" type="button" onClick={openImport} disabled={scanBusy || importBusy || Boolean(reconnectBusy)}>{scanBusy ? "Scanning PDFs…" : "Scan / import"}</button>} />
      {attention ? <div className="library-attention" role="alert"><div><strong>Library needs attention</strong><p>{resource.data.status.workspace_warnings[0] || "Review missing files, duplicates, or quarantine items before continuing."}</p></div><Link className="text-link" href="/settings">View diagnostics</Link></div> : null}

      <Section title="Papers">
        <Toolbar label="Library collection filters">
          <label className="search-shell library-toolbar__search"><span className="sr-only">Search papers</span><input type="search" value={q} placeholder="Search papers…" onChange={(event) => { setQ(event.target.value); resetCollection(); }} /></label>
          <input className="library-filter" aria-label="Filter by tag" value={tag} placeholder="Tag" onChange={(event) => { setTag(event.target.value); resetCollection(); }} />
          <input className="library-filter library-filter--year" aria-label="Filter by year" value={year} inputMode="numeric" maxLength={4} placeholder="Year" onChange={(event) => { setYear(event.target.value); resetCollection(); }} />
          <input className="library-filter" aria-label="Filter by reading status" value={readingStatus} placeholder="Reading status" onChange={(event) => { setReadingStatus(event.target.value); resetCollection(); }} />
          <select className="library-filter" aria-label="Filter library state" value={archiveStatus} onChange={(event) => { setArchiveStatus(event.target.value as "active" | "archived" | "all"); resetCollection(); }}><option value="active">Active</option><option value="archived">Archived</option><option value="all">All papers</option></select>
        </Toolbar>
        <div className={selectedPaperId ? "library-collection-layout library-collection-layout--with-inspector" : "library-collection-layout"}>
          <div className="library-collection-layout__table">
            {collection.status === "loading" ? <LoadingState label="Searching papers" /> : null}
            {collection.status === "unavailable" ? <UnavailableState description={collection.message} onRetry={collection.retry} /> : null}
            {collection.status === "error" || collection.status === "not-found" ? <ErrorState description={collection.message} onRetry={collection.retry} /> : null}
            {collection.status === "success" ? <>
              {collection.data.items.length === 0 ? <EmptyState title="No matching papers" description="Change the search or filters, or scan a PDF to add a paper." /> : <DataTableShell label="Paper collection"><table><thead><tr><th>Title</th><th>Author</th><th>Year</th><th>Reading</th><th>Tags</th></tr></thead><tbody>{collection.data.items.map((paper) => <tr className="library-paper-row" data-selected={selectedPaperId === paper.paper_id || undefined} key={paper.paper_id}><td><button className="library-paper-row__select" type="button" aria-pressed={selectedPaperId === paper.paper_id} onClick={() => selectPaper(paper.paper_id)}>{paper.title || "Untitled paper"}</button></td><td>{paper.first_author || "—"}</td><td>{paper.year || "—"}</td><td><div className="badge-row"><StatusBadge>{paper.status}</StatusBadge>{paper.missing_pdf ? <StatusBadge tone="danger">Missing PDF</StatusBadge> : null}</div></td><td>{paper.tags.length ? <span className="library-paper-row__tags">{paper.tags.join(", ")}</span> : <span className="muted-text">—</span>}</td></tr>)}</tbody></table></DataTableShell>}
              <div className="library-pagination"><span className="toolbar-note">{collection.data.total} matching paper{collection.data.total === 1 ? "" : "s"}</span><div className="reader-editor__actions"><button className="reader-control reader-control--secondary" type="button" disabled={offset === 0} onClick={() => changePage(Math.max(0, offset - PAGE_SIZE))}>Previous</button><button className="reader-control reader-control--secondary" type="button" disabled={!collection.data.has_more} onClick={() => changePage(offset + PAGE_SIZE)}>Next</button></div></div>
            </> : null}
          </div>
          {selectedPaperId ? <LibraryPaperInspector paperId={selectedPaperId} onDismiss={closeInspector} onEnrich={previewEnrichment} enrichmentBusy={enrichmentBusy} enrichmentContent={enrichmentPaperId === selectedPaperId ? <MetadataEnrichmentPanel enrichment={enrichment} error={enrichmentError} busy={enrichmentBusy} selectedFields={selectedFields} onToggleField={toggleField} onApply={applyEnrichment} onRetry={() => previewEnrichment(selectedPaperId)} onClose={() => { setEnrichmentPaperId(""); setEnrichment(null); setSelectedFields([]); }} /> : undefined} /> : null}
        </div>
      </Section>

      {showImport ? <Section title="Scan and import PDFs" description="Preview PDFs first, then choose the files to add." actions={<button className="reader-control reader-control--secondary" type="button" onClick={() => setShowImport(false)}>Close</button>}>
        {scanError ? <ErrorState title="PDF scan unavailable" description={scanError} onRetry={scanPdfs} /> : null}
        {scan?.status === "unavailable" ? <UnavailableState title="PDF scan unavailable" description={scan.message} onRetry={scanPdfs} /> : null}
        {scan?.status === "ok" ? <div className="pdf-import-workflow"><p className="pdf-import-workflow__summary" role="status">{scan.message}</p>{scan.candidates.length === 0 ? <EmptyState title="No PDFs found" description="Add PDF files to the managed papers directory and scan when ready." /> : <DataTableShell label="PDF scan candidates"><table><thead><tr><th>Select</th><th>PDF</th><th>Status</th><th>Details</th><th>Repair</th></tr></thead><tbody>{scan.candidates.map((candidate) => <tr key={candidate.relative_path}><td><input aria-label={`Select ${candidate.relative_path}`} type="checkbox" checked={selectedPaths.includes(candidate.relative_path)} disabled={!candidate.can_import || importBusy} onChange={() => toggleSelection(candidate.relative_path)} /></td><td><strong>{candidate.filename}</strong><small className="mono-id">{candidate.relative_path}</small></td><td><StatusBadge tone={scanTone(candidate.status)}>{candidate.status.replaceAll("_", " ")}</StatusBadge></td><td>{candidate.message}</td><td>{candidate.can_reconnect ? <button className="reader-control reader-control--secondary" type="button" disabled={Boolean(reconnectBusy)} onClick={() => reconnect(candidate.reconnect_paper_id, candidate.relative_path)}>{reconnectBusy === candidate.relative_path ? "Reconnecting…" : "Reconnect existing Paper"}</button> : candidate.status === "reconnect_ambiguous" ? <span className="muted-text">Manual review required</span> : "—"}</td></tr>)}</tbody></table></DataTableShell>}{scan.candidates.some((candidate) => candidate.can_import) ? <div className="reader-editor__actions"><button className="reader-control" type="button" onClick={importSelected} disabled={!selectedPaths.length || importBusy || scanBusy}>{importBusy ? "Importing selected PDFs…" : `Import selected (${selectedPaths.length})`}</button><span className="toolbar-note">Only new PDFs can be selected. Duplicates and reconnects do not create a second paper.</span></div> : null}</div> : null}
        {importError ? <ErrorState title="PDF command unavailable" description={importError} onRetry={scanPdfs} /> : null}
        {reconnectMessage ? <p className="reader-editor__status" role="status">{reconnectMessage}</p> : null}
        {importResult ? <div className="pdf-import-result" role="status"><p><strong>{importResult.message}</strong></p><ul>{importResult.results.map((result) => <li key={result.relative_path}><StatusBadge tone={scanTone(result.status)}>{result.status.replaceAll("_", " ")}</StatusBadge> {result.filename}: {result.message}{result.paper_id ? <Link className="text-link" href={`/papers/${encodeURIComponent(result.paper_id)}`}>Open Paper Detail</Link> : null}</li>)}</ul></div> : null}
      </Section> : null}
    </div>
  );
}

function MetadataEnrichmentPanel({ enrichment, error, busy, selectedFields, onToggleField, onApply, onRetry, onClose }: {
  enrichment: MetadataEnrichmentPreview | null;
  error: string;
  busy: boolean;
  selectedFields: Array<keyof EditablePaperMetadata>;
  onToggleField: (field: keyof EditablePaperMetadata) => void;
  onApply: () => void;
  onRetry: () => void;
  onClose: () => void;
}) {
  if (error) return <ErrorState title="Metadata preview unavailable" description={error} onRetry={onRetry} />;
  if (busy && !enrichment) return <LoadingState label="Fetching metadata candidates" />;
  if (!enrichment) return null;
  return <div className="metadata-enrichment"><div className="library-paper-inspector__enrichment-heading"><h3>Metadata enrichment</h3><p>Review each candidate before applying it.</p></div><DataTableShell label="Metadata candidate comparison"><table><thead><tr><th>Apply</th><th>Field</th><th>Current</th><th>Candidate</th></tr></thead><tbody>{enrichment.fields.map((field) => { const selectable = Boolean(field.candidate_value) && field.state !== "unchanged"; return <tr key={field.field}><td><input type="checkbox" aria-label={`Select ${FIELD_LABELS[field.field]} candidate`} checked={selectedFields.includes(field.field)} disabled={!selectable || busy} onChange={() => onToggleField(field.field)} /></td><td>{FIELD_LABELS[field.field]}</td><td>{field.current_value || "—"}</td><td>{field.candidate_value || "Unavailable"}</td></tr>; })}</tbody></table></DataTableShell>{enrichment.candidate_sources.length ? <p className="metadata-enrichment__sources">Candidate sources: {enrichment.candidate_sources.join(", ")}</p> : null}{enrichment.diagnostics.length ? <details className="metadata-enrichment__details"><summary>Candidate details</summary><ul>{enrichment.diagnostics.map((diagnostic) => <li key={diagnostic}>{diagnostic}</li>)}</ul></details> : null}<div className="reader-editor__actions"><button className="reader-control" type="button" disabled={!selectedFields.length || busy} onClick={onApply}>{busy ? "Applying…" : "Apply selected fields"}</button><button className="reader-control reader-control--secondary" type="button" disabled={busy} onClick={onRetry}>Fetch fresh candidates</button><button className="reader-control reader-control--secondary" type="button" disabled={busy} onClick={onClose}>Close</button></div></div>;
}
