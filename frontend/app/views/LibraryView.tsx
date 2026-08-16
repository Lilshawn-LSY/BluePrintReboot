"use client";

import Link from "next/link";
import { useState } from "react";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { DataTableShell } from "../components/DataTableShell";
import { DetailPanel } from "../components/DetailPanel";
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
  return error instanceof ApiClientError ? error.message : "The managed PDF command could not be completed.";
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

  const resetCollection = () => setOffset(0);
  const scanPdfs = async () => {
    setScanBusy(true); setScanError(""); setImportError(""); setImportResult(null); setReconnectMessage("");
    try { setScan(await apiClient.scanManagedPdfs()); setSelectedPaths([]); }
    catch (error) { setScan(null); setScanError(friendlyCommandError(error)); }
    finally { setScanBusy(false); }
  };
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

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Paper collection" title="Library" description="Scan and register managed PDFs, then browse, search, enrich, and open the Papers in your local collection." />
      {resource.status === "loading" ? <LoadingState label="Reading library status" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "error" || resource.status === "not-found" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? <Section title="Library status" description="Current read-only health indicators."><div className="summary-strip summary-strip--six"><div><span>Overall</span><StatusBadge tone={resource.data.health.overall_state === "healthy" ? "healthy" : "warning"}>{resource.data.health.overall_state}</StatusBadge></div><div><span>Active</span><strong>{resource.data.status.active_count}</strong></div><div><span>Missing PDFs</span><strong>{resource.data.status.missing_count}</strong></div><div><span>Duplicates</span><strong>{resource.data.status.duplicate_count}</strong></div><div><span>Archived</span><strong>{resource.data.status.archived_count}</strong></div><div><span>Quarantine</span><strong>{resource.data.status.quarantine_count}</strong></div></div>{resource.data.status.workspace_warnings.length ? <ul className="warning-list">{resource.data.status.workspace_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul> : null}</Section> : null}

      <Section title="Papers" description="Server-backed metadata search and exact filters apply across the registered collection before pagination.">
        <Toolbar label="Library collection filters">
          <label className="search-shell"><span className="sr-only">Search Papers</span><input type="search" value={q} placeholder="Search title, authors, journal, DOI, tags, keywords" onChange={(event) => { setQ(event.target.value); resetCollection(); }} /></label>
          <input aria-label="Filter by tag" value={tag} placeholder="Exact tag" onChange={(event) => { setTag(event.target.value); resetCollection(); }} />
          <input aria-label="Filter by year" value={year} inputMode="numeric" maxLength={4} placeholder="Year" onChange={(event) => { setYear(event.target.value); resetCollection(); }} />
          <input aria-label="Filter by reading status" value={readingStatus} placeholder="Reading status" onChange={(event) => { setReadingStatus(event.target.value); resetCollection(); }} />
          <select aria-label="Filter lifecycle" value={archiveStatus} onChange={(event) => { setArchiveStatus(event.target.value as "active" | "archived" | "all"); resetCollection(); }}><option value="active">Active</option><option value="archived">Archived</option><option value="all">All lifecycle states</option></select>
        </Toolbar>
        {collection.status === "loading" ? <LoadingState label="Searching Papers" /> : null}
        {collection.status === "unavailable" ? <UnavailableState description={collection.message} onRetry={collection.retry} /> : null}
        {collection.status === "error" || collection.status === "not-found" ? <ErrorState description={collection.message} onRetry={collection.retry} /> : null}
        {collection.status === "success" ? <>{collection.data.items.length === 0 ? <EmptyState title="No matching Papers" description="Change the search or filters, or scan a managed PDF to register a Paper." /> : <DataTableShell label="Library Paper collection"><table><thead><tr><th>Title</th><th>Author</th><th>Year</th><th>Status</th><th>Tags</th><th>Actions</th></tr></thead><tbody>{collection.data.items.map((paper) => <tr key={paper.paper_id}><td><Link className="paper-link" href={`/papers/${encodeURIComponent(paper.paper_id)}`}>{paper.title}<small className="mono-id">{paper.paper_id}</small></Link></td><td>{paper.first_author || "—"}</td><td>{paper.year || "—"}</td><td><StatusBadge>{paper.status}</StatusBadge>{paper.missing_pdf ? <StatusBadge tone="danger">Missing PDF</StatusBadge> : null}</td><td>{paper.tags.length ? paper.tags.join(", ") : "—"}</td><td><div className="reader-editor__actions"><Link className="text-link" href={`/papers/${encodeURIComponent(paper.paper_id)}`}>Detail</Link>{!paper.missing_pdf ? <Link className="text-link" href={`/papers/${encodeURIComponent(paper.paper_id)}/reader`}>Reader</Link> : null}<button className="reader-control reader-control--secondary" type="button" disabled={enrichmentBusy} onClick={() => previewEnrichment(paper.paper_id)}>{enrichmentPaperId === paper.paper_id && enrichmentBusy ? "Loading…" : "Enrich"}</button></div></td></tr>)}</tbody></table></DataTableShell>}<div className="reader-editor__actions"><span className="toolbar-note">{collection.data.total} matching Paper{collection.data.total === 1 ? "" : "s"}</span><button className="reader-control reader-control--secondary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button><button className="reader-control reader-control--secondary" type="button" disabled={!collection.data.has_more} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button></div></> : null}
      </Section>

      {enrichmentPaperId ? <Section title="Metadata enrichment" description="Candidates are a preview only. Select individual fields before the existing revision-protected metadata command is used.">{enrichmentError ? <ErrorState description={enrichmentError} onRetry={() => previewEnrichment(enrichmentPaperId)} /> : null}{enrichment ? <><DataTableShell label="Metadata candidate comparison"><table><thead><tr><th>Apply</th><th>Field</th><th>Current</th><th>Candidate</th><th>Source</th></tr></thead><tbody>{enrichment.fields.map((field) => { const selectable = Boolean(field.candidate_value) && field.state !== "unchanged"; return <tr key={field.field}><td><input type="checkbox" aria-label={`Select ${FIELD_LABELS[field.field]} candidate`} checked={selectedFields.includes(field.field)} disabled={!selectable || enrichmentBusy} onChange={() => toggleField(field.field)} /></td><td>{FIELD_LABELS[field.field]}</td><td>{field.current_value || "—"}</td><td>{field.candidate_value || "Unavailable"}</td><td>{field.source || "No source"} · {field.state}</td></tr>; })}</tbody></table></DataTableShell>{enrichment.diagnostics.length ? <ul className="warning-list">{enrichment.diagnostics.map((diagnostic) => <li key={diagnostic}>{diagnostic}</li>)}</ul> : null}<div className="reader-editor__actions"><button className="reader-control" type="button" disabled={!selectedFields.length || enrichmentBusy} onClick={applyEnrichment}>{enrichmentBusy ? "Applying…" : "Apply selected fields"}</button><button className="reader-control reader-control--secondary" type="button" disabled={enrichmentBusy} onClick={() => previewEnrichment(enrichmentPaperId)}>Fetch fresh candidates</button><button className="reader-control reader-control--secondary" type="button" onClick={() => { setEnrichmentPaperId(""); setEnrichment(null); setSelectedFields([]); }}>Close</button></div></> : enrichmentBusy ? <LoadingState label="Fetching metadata candidates" /> : null}</Section> : null}

      <Section title="PDF scan and import" description="Place PDFs in the managed directory, scan to preview them, then explicitly register selected new files. Scanning alone never changes the Paper registry." actions={<button className="reader-control" type="button" onClick={scanPdfs} disabled={scanBusy || importBusy || Boolean(reconnectBusy)}>{scanBusy ? "Scanning PDFs…" : "Scan PDFs"}</button>}>
        {scanError ? <ErrorState title="PDF scan unavailable" description={scanError} onRetry={scanPdfs} /> : null}
        {scan?.status === "unavailable" ? <UnavailableState title="PDF scan unavailable" description={scan.message} onRetry={scanPdfs} /> : null}
        {scan?.status === "ok" ? <div className="pdf-import-workflow"><p className="pdf-import-workflow__summary" role="status">{scan.message}</p>{scan.candidates.length === 0 ? <EmptyState title="No managed PDFs found" description="Add PDF files to the managed papers directory and scan when ready." /> : <DataTableShell label="Managed PDF scan candidates"><table><thead><tr><th>Select</th><th>PDF</th><th>Status</th><th>Details</th><th>Repair</th></tr></thead><tbody>{scan.candidates.map((candidate) => <tr key={candidate.relative_path}><td><input aria-label={`Select ${candidate.relative_path}`} type="checkbox" checked={selectedPaths.includes(candidate.relative_path)} disabled={!candidate.can_import || importBusy} onChange={() => toggleSelection(candidate.relative_path)} /></td><td><strong>{candidate.filename}</strong><small className="mono-id">{candidate.relative_path}</small></td><td><StatusBadge tone={scanTone(candidate.status)}>{candidate.status.replaceAll("_", " ")}</StatusBadge></td><td>{candidate.message}</td><td>{candidate.can_reconnect ? <button className="reader-control reader-control--secondary" type="button" disabled={Boolean(reconnectBusy)} onClick={() => reconnect(candidate.reconnect_paper_id, candidate.relative_path)}>{reconnectBusy === candidate.relative_path ? "Reconnecting…" : "Reconnect existing Paper"}</button> : candidate.status === "reconnect_ambiguous" ? <span className="muted-text">Manual review required</span> : "—"}</td></tr>)}</tbody></table></DataTableShell>}{scan.candidates.some((candidate) => candidate.can_import) ? <div className="reader-editor__actions"><button className="reader-control" type="button" onClick={importSelected} disabled={!selectedPaths.length || importBusy || scanBusy}>{importBusy ? "Importing selected PDFs…" : `Import selected (${selectedPaths.length})`}</button><span className="toolbar-note">Only new PDFs can be selected; exact duplicates and reconnects never create a second Paper.</span></div> : null}</div> : null}
        {importError ? <ErrorState title="PDF command unavailable" description={importError} onRetry={scanPdfs} /> : null}
        {reconnectMessage ? <p className="reader-editor__status" role="status">{reconnectMessage}</p> : null}
        {importResult ? <div className="pdf-import-result" role="status"><p><strong>{importResult.message}</strong></p><ul>{importResult.results.map((result) => <li key={result.relative_path}><StatusBadge tone={scanTone(result.status)}>{result.status.replaceAll("_", " ")}</StatusBadge> {result.filename}: {result.message}{result.paper_id ? <Link className="text-link" href={`/papers/${encodeURIComponent(result.paper_id)}`}>Open Paper Detail</Link> : null}</li>)}</ul></div> : null}
      </Section>
      <DetailPanel title="Bounded maintenance"><p>Library includes scan, import, duplicate detection, missing-PDF visibility, and explicit exact-content reconnect. Quarantine, cleanup, backup, and destructive repair remain outside this web workflow.</p></DetailPanel>
    </div>
  );
}
