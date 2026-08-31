"use client";

import { ArrowLeft, FileText, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiClientError, apiClient } from "../lib/api/client";
import type { FullTextCacheState } from "../lib/api/types";
import { initialFullTextUiState, transitionFullTextUiState } from "../lib/full-text/workflow-state.mjs";
import { StatusBadge } from "./StatusBadge";


const STATE_LABELS: Record<FullTextCacheState, string> = {
  not_extracted: "Not extracted",
  success: "Ready",
  cached: "Cached",
  stale: "Stale",
  failed: "Failed",
  ocr_needed: "OCR needed",
};


function statusTone(state: FullTextCacheState): "slate" | "blue" | "green" | "amber" | "rose" {
  if (state === "failed") return "rose";
  if (state === "stale" || state === "ocr_needed") return "amber";
  if (state === "success") return "green";
  if (state === "cached") return "blue";
  return "slate";
}


function operationError(error: unknown): string {
  if (error instanceof ApiClientError && error.kind === "not-found") return "This Paper is no longer available.";
  return "Full-text state could not be updated. The existing cache was not discarded.";
}


export function FullTextWorkspace({ paperId }: { paperId: string }) {
  const [ui, setUi] = useState(initialFullTextUiState);

  const loadStatus = async () => {
    setUi((state) => transitionFullTextUiState(state, { type: "status-loading" }));
    try {
      const status = await apiClient.getFullTextStatus(paperId);
      setUi((state) => transitionFullTextUiState(state, { type: "status-loaded", status }));
    } catch (error) {
      setUi((state) => transitionFullTextUiState(state, { type: "operation-failed", message: operationError(error) }));
    }
  };

  useEffect(() => {
    let current = true;
    void apiClient.getFullTextStatus(paperId)
      .then((status) => {
        if (current) setUi((state) => transitionFullTextUiState(state, { type: "status-loaded", status }));
      })
      .catch((error) => {
        if (current) setUi((state) => transitionFullTextUiState(state, { type: "operation-failed", message: operationError(error) }));
      });
    return () => { current = false; };
  }, [paperId]);

  const extract = async () => {
    if (!ui.data || ui.phase === "working") return;
    const force = ui.data.state !== "not_extracted";
    setUi((state) => transitionFullTextUiState(state, { type: "operation-started" }));
    try {
      const document = await apiClient.extractFullText(paperId, force);
      setUi((state) => transitionFullTextUiState(state, { type: "document-loaded", document, open: false }));
    } catch (error) {
      setUi((state) => transitionFullTextUiState(state, { type: "operation-failed", message: operationError(error) }));
    }
  };

  const openFullText = async () => {
    if (ui.phase === "working") return;
    setUi((state) => transitionFullTextUiState(state, { type: "operation-started" }));
    try {
      const document = await apiClient.getFullText(paperId);
      setUi((state) => transitionFullTextUiState(state, { type: "document-loaded", document, open: true }));
    } catch (error) {
      setUi((state) => transitionFullTextUiState(state, { type: "operation-failed", message: operationError(error) }));
    }
  };

  const data = ui.data;
  const busy = ui.phase === "loading" || ui.phase === "working";
  const extractedPages = data?.page_count ? `${data.page_count} page${data.page_count === 1 ? "" : "s"} extracted` : "Extracted text is available.";
  return (
    <section className="reader-utility-section full-text-workspace" aria-labelledby="full-text-title">
      <div className="reader-note__heading">
        <div>
          <h2 id="full-text-title">Full Text</h2>
        </div>
        <StatusBadge tone={data ? statusTone(data.state) : ui.phase === "error" ? "rose" : "slate"}>
          {data ? STATE_LABELS[data.state] : ui.phase === "error" ? "Unavailable" : "Loading"}
        </StatusBadge>
      </div>

      <p className="reader-editor__status" role="status" aria-live="polite">
        {ui.message || (data?.state === "not_extracted" ? "No extracted text yet." : data?.state === "failed" || data?.state === "ocr_needed" ? "Text extraction failed. This PDF may require OCR." : extractedPages)}
      </p>

      <div className="reader-editor__actions">
        {data?.has_content ? (
          <button className="reader-control" type="button" disabled={busy} onClick={openFullText}>
            <FileText size={15} />View text
          </button>
        ) : null}
        {data?.can_extract ? (
          <button className={data.has_content ? "reader-control reader-control--secondary" : "reader-control"} type="button" disabled={busy} onClick={extract}>
            <RefreshCw size={15} />{ui.phase === "working" ? "Extracting…" : data.state === "not_extracted" ? "Extract text" : "Re-extract"}
          </button>
        ) : null}
        {ui.phase === "error" ? (
          <button className="reader-control reader-control--secondary" type="button" onClick={loadStatus}>
            <RefreshCw size={15} />Retry Status
          </button>
        ) : null}
      </div>

      {ui.viewerOpen ? (
        <div className="full-text-viewer" role="region" aria-label="Canonical extracted full text">
          <div className="full-text-viewer__heading">
            <strong>Extracted text</strong>
            <button className="reader-control reader-control--secondary" type="button" onClick={() => setUi((state) => transitionFullTextUiState(state, { type: "viewer-closed" }))}><ArrowLeft size={15} />Back</button>
          </div>
          <pre>{ui.content}</pre>
        </div>
      ) : null}
    </section>
  );
}
