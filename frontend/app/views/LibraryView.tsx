"use client";

import Link from "next/link";
import { useState } from "react";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { DataTableShell } from "../components/DataTableShell";
import { DetailPanel } from "../components/DetailPanel";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";
import type { ManagedPdfImportResponse, ManagedPdfScanResponse } from "../lib/api/types";

function scanTone(status: string): "healthy" | "warning" | "danger" | "neutral" {
  if (status === "new" || status === "imported") return "healthy";
  if (status === "already_registered") return "warning";
  if (status === "invalid" || status === "unavailable" || status === "missing") return "danger";
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
  const [scan, setScan] = useState<ManagedPdfScanResponse | null>(null);
  const [scanError, setScanError] = useState("");
  const [scanBusy, setScanBusy] = useState(false);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [importResult, setImportResult] = useState<ManagedPdfImportResponse | null>(null);
  const [importError, setImportError] = useState("");
  const [importBusy, setImportBusy] = useState(false);

  const scanPdfs = async () => {
    setScanBusy(true);
    setScanError("");
    setImportError("");
    setImportResult(null);
    try {
      const result = await apiClient.scanManagedPdfs();
      setScan(result);
      setSelectedPaths([]);
    } catch (error) {
      setScan(null);
      setScanError(friendlyCommandError(error));
    } finally {
      setScanBusy(false);
    }
  };

  const toggleSelection = (relativePath: string) => {
    setSelectedPaths((current) => current.includes(relativePath)
      ? current.filter((item) => item !== relativePath)
      : [...current, relativePath]);
  };

  const importSelected = async () => {
    if (selectedPaths.length === 0) return;
    setImportBusy(true);
    setImportError("");
    try {
      const result = await apiClient.importManagedPdfs(selectedPaths);
      setImportResult(result);
      setSelectedPaths([]);
      resource.retry();
    } catch (error) {
      setImportError(friendlyCommandError(error));
    } finally {
      setImportBusy(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Files and integrity" title="Library" description="Monitor PDF lifecycle, missing files, duplicates, quarantine, and recovery readiness. Reading workflows live under Papers." />
      {resource.status === "loading" ? <LoadingState label="Reading library status" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} /> : null}
      {resource.status === "error" || resource.status === "not-found" ? <ErrorState description={resource.message} /> : null}
      {resource.status === "success" ? (
        <>
          <Section title="Integrity summary" description="Current read-only health indicators; maintenance actions remain in Streamlit.">
            <div className="summary-strip summary-strip--six">
              <div><span>Overall</span><StatusBadge tone={resource.data.health.overall_state === "healthy" ? "healthy" : "warning"}>{resource.data.health.overall_state}</StatusBadge></div>
              <div><span>Missing PDFs</span><strong>{resource.data.status.missing_count}</strong></div>
              <div><span>Duplicates</span><strong>{resource.data.status.duplicate_count}</strong></div>
              <div><span>Corrupt state</span><strong>{resource.data.status.corrupt_count}</strong></div>
              <div><span>Quarantine</span><strong>{resource.data.status.quarantine_count}</strong></div>
              <div><span>Archived</span><strong>{resource.data.status.archived_count}</strong></div>
            </div>
          </Section>
          <Section title="Workspace warnings" description="Stable, non-sensitive guidance supplied by the API.">
            {resource.data.status.workspace_warnings.length === 0 ? <EmptyState title="No workspace warnings" description="The current library status does not report a maintenance warning." /> : <ul className="warning-list">{resource.data.status.workspace_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
          </Section>
          <Section
            title="PDF scan and import"
            description="Place PDFs in the managed papers directory, scan to preview them, then explicitly register selected new files. Scanning alone never changes the Paper registry."
            actions={<button className="reader-control" type="button" onClick={scanPdfs} disabled={scanBusy || importBusy}>{scanBusy ? "Scanning PDFs…" : "Scan PDFs"}</button>}
          >
            {scanError ? <ErrorState title="PDF scan unavailable" description={scanError} onRetry={scanPdfs} /> : null}
            {scan?.status === "unavailable" ? <UnavailableState title="PDF scan unavailable" description={scan.message} onRetry={scanPdfs} /> : null}
            {scan?.status === "ok" ? (
              <div className="pdf-import-workflow">
                <p className="pdf-import-workflow__summary" role="status">{scan.message}</p>
                {scan.candidates.length === 0 ? <EmptyState title="No managed PDFs found" description="Add PDF files to papers/ and choose Scan PDFs when you are ready to preview them." /> : (
                  <DataTableShell label="Managed PDF scan candidates">
                    <table>
                      <thead><tr><th>Select</th><th>PDF</th><th>Status</th><th>Details</th></tr></thead>
                      <tbody>{scan.candidates.map((candidate) => (
                        <tr key={candidate.relative_path}>
                          <td><input aria-label={`Select ${candidate.relative_path}`} type="checkbox" checked={selectedPaths.includes(candidate.relative_path)} disabled={!candidate.can_import || importBusy} onChange={() => toggleSelection(candidate.relative_path)} /></td>
                          <td><strong>{candidate.filename}</strong><small className="mono-id">{candidate.relative_path}</small></td>
                          <td><StatusBadge tone={scanTone(candidate.status)}>{candidate.status.replaceAll("_", " ")}</StatusBadge></td>
                          <td>{candidate.message}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </DataTableShell>
                )}
                {scan.candidates.length > 0 ? <div className="reader-editor__actions"><button className="reader-control" type="button" onClick={importSelected} disabled={selectedPaths.length === 0 || importBusy || scanBusy}>{importBusy ? "Importing selected PDFs…" : `Import selected (${selectedPaths.length})`}</button><span className="toolbar-note">Only new PDFs can be selected. Metadata enrichment remains a separate Reader action.</span></div> : null}
              </div>
            ) : null}
            {importError ? <ErrorState title="PDF import unavailable" description={importError} onRetry={importSelected} /> : null}
            {importResult ? (
              <div className="pdf-import-result" role="status">
                <p><strong>{importResult.message}</strong></p>
                <ul>{importResult.results.map((result) => <li key={result.relative_path}><StatusBadge tone={scanTone(result.status)}>{result.status.replaceAll("_", " ")}</StatusBadge> <span>{result.filename}: {result.message}</span>{result.paper_id ? <><Link className="text-link" href={`/papers/${encodeURIComponent(result.paper_id)}`}>Open Paper</Link><Link className="text-link" href={`/papers/${encodeURIComponent(result.paper_id)}/reader`}>Open Reader</Link></> : null}</li>)}</ul>
                {importResult.imported_count > 0 ? <Link className="text-link" href="/papers">View imported Papers in the collection</Link> : null}
              </div>
            ) : null}
          </Section>
          <DetailPanel title="Other maintenance availability"><p>Duplicate decisions, archive changes, repair, quarantine, restore, and backup remain available only in the primary Streamlit interface.</p></DetailPanel>
        </>
      ) : null}
    </div>
  );
}
