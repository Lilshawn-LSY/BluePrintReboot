"use client";

import { FileText, RefreshCw, X } from "lucide-react";
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


function statusTone(state: FullTextCacheState): "neutral" | "accent" | "warning" | "danger" {
  if (state === "failed") return "danger";
  if (state === "stale" || state === "ocr_needed") return "warning";
  if (state === "cached" || state === "success") return "accent";
  return "neutral";
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
  return (
    <section className="reader-editor full-text-workspace" aria-labelledby="full-text-title">
      <div className="reader-note__heading">
        <div>
          <p className="eyebrow">Local extraction cache</p>
          <h2 id="full-text-title">Full Text</h2>
        </div>
        <StatusBadge tone={data ? statusTone(data.state) : ui.phase === "error" ? "danger" : "neutral"}>
          {data ? STATE_LABELS[data.state] : ui.phase === "error" ? "Unavailable" : "Loading"}
        </StatusBadge>
      </div>

      <p className="reader-editor__status" role="status" aria-live="polite">
        {ui.message || data?.message || "Reading local extraction state…"}
      </p>

      {data && data.state !== "not_extracted" ? (
        <dl className="full-text-metadata">
          <div><dt>Provider</dt><dd>{data.provider || data.source || "Unavailable"}{data.provider_version ? ` ${data.provider_version}` : ""}</dd></div>
          <div><dt>Pages</dt><dd>{data.page_count || "Unavailable"}</dd></div>
          <div><dt>Characters</dt><dd>{data.char_count.toLocaleString()}</dd></div>
          <div><dt>Classification</dt><dd>{data.classification}</dd></div>
        </dl>
      ) : null}

      {data?.ocr_needed_pages.length ? (
        <p className="full-text-ocr-pages">OCR needed: pages {data.ocr_needed_pages.join(", ")}</p>
      ) : null}

      <div className="reader-editor__actions">
        {data?.has_content ? (
          <button className="reader-control" type="button" disabled={busy} onClick={openFullText}>
            <FileText size={15} />Open Full Text
          </button>
        ) : null}
        {data?.can_extract ? (
          <button className={data.has_content ? "reader-control reader-control--secondary" : "reader-control"} type="button" disabled={busy} onClick={extract}>
            <RefreshCw size={15} />{ui.phase === "working" ? "Extracting…" : data.state === "not_extracted" ? "Extract Full Text" : data.state === "failed" ? "Retry Extraction" : "Re-extract"}
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
            <span>{data?.content_format === "markdown" ? "Markdown" : "Plain text"}</span>
            <button className="icon-button" type="button" title="Close full text" aria-label="Close full text" onClick={() => setUi((state) => transitionFullTextUiState(state, { type: "viewer-closed" }))}>
              <X size={16} />
            </button>
          </div>
          <pre>{ui.content}</pre>
        </div>
      ) : null}
    </section>
  );
}
