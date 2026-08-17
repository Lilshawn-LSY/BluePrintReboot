"use client";

import { AlertCircle, ChevronLeft, ChevronRight, ExternalLink, LoaderCircle, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { paperPdfUrl } from "../lib/api/client";
import { createPdfLoadingTask, createPdfTextLayer, readPdfNetworkDiagnostics } from "../lib/pdf/pdfjs-adapter";
import {
  DEFAULT_ZOOM,
  MAX_ZOOM,
  MIN_ZOOM,
  PdfReaderController,
  type PdfReaderDiagnostics,
  type PdfReaderState,
} from "../lib/pdf/reader-controller.mjs";
import { readPageSelection, type PdfPageSelection } from "../lib/pdf/selection-coordinates.mjs";


const INITIAL_STATE: PdfReaderState = {
  mode: "loading",
  pageNumber: 1,
  totalPages: 0,
  zoom: DEFAULT_ZOOM,
  rendering: false,
  errorKind: null,
  message: "",
};

const INITIAL_DIAGNOSTICS: PdfReaderDiagnostics = {
  documentLoadCount: 0,
  renderCount: 0,
  renderCancellationCount: 0,
  documentLoadDurationMs: null,
  firstPageRenderDurationMs: null,
  requestCount: null,
  rangeRequestCount: null,
  fullRequestCount: null,
  requestMode: "pdfjs-auto",
};

function safeLifecycleErrorName(error: unknown): string {
  return error && typeof error === "object" && "name" in error && typeof error.name === "string"
    ? error.name
    : "Error";
}

function observeLifecyclePromise(promise: Promise<void>, phase: "load" | "cleanup"): void {
  promise.catch((error: unknown) => {
    if (
      process.env.NODE_ENV !== "production"
      && process.env.NEXT_PUBLIC_BLUEPRINT_READER_DIAGNOSTICS === "1"
    ) {
      console.warn("PDF.js Reader lifecycle promise rejected.", {
        phase,
        errorName: safeLifecycleErrorName(error),
      });
    }
  });
}


function NativePdfFallback({ pdfUrl, onRetry }: { pdfUrl: string; onRetry: () => void }) {
  return (
    <div className="reader-native-fallback-shell" role="region" aria-label="Native browser PDF fallback">
      <div className="reader-fallback-banner" role="status">
        <strong>Native browser fallback active</strong>
        <span>PDF.js is not mounted while this fallback is displayed.</span>
      </div>
      <object className="reader-pdf-viewer" data={pdfUrl} type="application/pdf" aria-label="Native browser PDF fallback viewer">
        <div className="reader-native-fallback">
          <h2>Browser PDF viewer unavailable</h2>
          <p>This browser cannot display the managed PDF inline.</p>
          <a className="text-link" href={pdfUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} />Open the managed PDF in a browser tab</a>
        </div>
      </object>
      <div className="reader-fallback-actions">
        <button className="reader-control" type="button" onClick={onRetry}>Retry PDF.js Reader</button>
      </div>
    </div>
  );
}


function ReaderDiagnostics({ diagnostics }: { diagnostics: PdfReaderDiagnostics }) {
  return (
    <details className="reader-diagnostics">
      <summary>Reader diagnostics (development only)</summary>
      <dl>
        <div><dt>Document loads</dt><dd>{diagnostics.documentLoadCount}</dd></div>
        <div><dt>Page renders</dt><dd>{diagnostics.renderCount}</dd></div>
        <div><dt>Render cancellations</dt><dd>{diagnostics.renderCancellationCount}</dd></div>
        <div><dt>First page render</dt><dd>{diagnostics.firstPageRenderDurationMs === null ? "Pending" : `${Math.round(diagnostics.firstPageRenderDurationMs)} ms`}</dd></div>
        <div><dt>Observed PDF requests</dt><dd>{diagnostics.requestCount ?? "Unavailable"}</dd></div>
        <div><dt>Observed Range responses</dt><dd>{diagnostics.rangeRequestCount ?? "Unavailable"}</dd></div>
        <div><dt>Request mode</dt><dd>{diagnostics.requestMode}</dd></div>
      </dl>
    </details>
  );
}


export function PdfJsReader({
  paperId,
  onSelectionChange,
}: {
  paperId: string;
  onSelectionChange?: (selection: PdfPageSelection | null) => void;
}) {
  const pdfUrl = useMemo(() => paperPdfUrl(paperId), [paperId]);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pageSurfaceRef = useRef<HTMLDivElement | null>(null);
  const textLayerRef = useRef<HTMLDivElement | null>(null);
  const controllerRef = useRef<PdfReaderController | null>(null);
  const lifecycleGenerationRef = useRef(0);
  const [state, setState] = useState<PdfReaderState>(INITIAL_STATE);
  const [diagnostics, setDiagnostics] = useState<PdfReaderDiagnostics>(INITIAL_DIAGNOSTICS);
  const [pageInput, setPageInput] = useState("1");
  const diagnosticsEnabled = process.env.NODE_ENV !== "production"
    && process.env.NEXT_PUBLIC_BLUEPRINT_READER_DIAGNOSTICS === "1";

  useEffect(() => {
    const lifecycleGeneration = ++lifecycleGenerationRef.current;
    const baseline = readPdfNetworkDiagnostics(pdfUrl);
    const controller = new PdfReaderController({
      createLoadingTask: createPdfLoadingTask,
      createTextLayer: createPdfTextLayer,
      isCurrent: () => (
        lifecycleGenerationRef.current === lifecycleGeneration
        && controllerRef.current === controller
      ),
      getCanvas: () => (
        lifecycleGenerationRef.current === lifecycleGeneration
        && controllerRef.current === controller
          ? canvasRef.current
          : null
      ),
      getTextLayerContainer: () => (
        lifecycleGenerationRef.current === lifecycleGeneration
        && controllerRef.current === controller
          ? textLayerRef.current
          : null
      ),
      getOutputScale: () => window.devicePixelRatio || 1,
      onState: (nextState) => {
        setState(nextState);
        setPageInput(String(nextState.pageNumber));
      },
      onDiagnostics: setDiagnostics,
      getNetworkDiagnostics: (url) => {
        const current = readPdfNetworkDiagnostics(url);
        return {
          ...current,
          requestCount: Math.max(0, current.requestCount - baseline.requestCount),
          rangeRequestCount: Math.max(0, current.rangeRequestCount - baseline.rangeRequestCount),
          fullRequestCount: Math.max(0, current.fullRequestCount - baseline.fullRequestCount),
        };
      },
    });
    controllerRef.current = controller;
    observeLifecyclePromise(controller.load(pdfUrl), "load");
    return () => {
      if (lifecycleGenerationRef.current === lifecycleGeneration) {
        lifecycleGenerationRef.current += 1;
      }
      if (controllerRef.current === controller) controllerRef.current = null;
      observeLifecyclePromise(controller.destroy(), "cleanup");
    };
  }, [pdfUrl]);

  const commitPageInput = () => {
    const requestedPage = Number.parseInt(pageInput, 10);
    if (!Number.isFinite(requestedPage)) {
      setPageInput(String(state.pageNumber));
      return;
    }
    void controllerRef.current?.setPage(requestedPage);
  };

  const publishSelection = () => {
    if (!onSelectionChange || !pageSurfaceRef.current) return;
    onSelectionChange(readPageSelection({
      pageNumber: state.pageNumber,
      pageElement: pageSurfaceRef.current,
    }));
  };

  if (state.mode === "fallback") {
    return <NativePdfFallback pdfUrl={pdfUrl} onRetry={() => void controllerRef.current?.retry()} />;
  }

  const controlsReady = state.mode === "ready";
  const canvasActive = state.mode === "ready" && !state.errorKind;
  return (
    <div className="pdfjs-reader">
      <div className="reader-toolbar" role="toolbar" aria-label="PDF page and zoom controls">
        <div className="reader-toolbar__group" aria-label="Page navigation">
          <button className="reader-control" type="button" aria-label="Previous PDF page" disabled={!controlsReady || state.pageNumber <= 1} onClick={() => void controllerRef.current?.previousPage()}><ChevronLeft size={16} />Previous</button>
          <label className="reader-page-field">
            <span>Page</span>
            <input
              aria-label="PDF page number"
              type="number"
              inputMode="numeric"
              min={1}
              max={Math.max(1, state.totalPages)}
              value={pageInput}
              disabled={!controlsReady}
              onChange={(event) => setPageInput(event.target.value)}
              onBlur={commitPageInput}
              onKeyDown={(event) => { if (event.key === "Enter") commitPageInput(); }}
            />
            <span aria-live="polite">of {state.totalPages || "?"}</span>
          </label>
          <button className="reader-control" type="button" aria-label="Next PDF page" disabled={!controlsReady || state.pageNumber >= state.totalPages} onClick={() => void controllerRef.current?.nextPage()}>Next<ChevronRight size={16} /></button>
        </div>
        <div className="reader-toolbar__group" aria-label="PDF zoom controls">
          <button className="reader-control" type="button" aria-label="Zoom out" disabled={!controlsReady || state.zoom <= MIN_ZOOM} onClick={() => void controllerRef.current?.zoomOut()}><ZoomOut size={16} />Zoom out</button>
          <output className="reader-zoom-value" aria-live="polite">{Math.round(state.zoom * 100)}%</output>
          <button className="reader-control" type="button" aria-label="Zoom in" disabled={!controlsReady || state.zoom >= MAX_ZOOM} onClick={() => void controllerRef.current?.zoomIn()}><ZoomIn size={16} />Zoom in</button>
          <button className="reader-control" type="button" aria-label="Reset PDF zoom" disabled={!controlsReady || state.zoom === DEFAULT_ZOOM} onClick={() => void controllerRef.current?.resetZoom()}><RotateCcw size={16} />Reset</button>
        </div>
      </div>

      <div className="reader-canvas-viewport">
        <div
          ref={pageSurfaceRef}
          className={canvasActive ? "reader-page-surface" : "reader-page-surface reader-page-surface--inactive"}
          onMouseUp={publishSelection}
          onKeyUp={publishSelection}
        >
          <canvas ref={canvasRef} className="reader-canvas" role="img" aria-label={`PDF page ${state.pageNumber}${state.totalPages ? ` of ${state.totalPages}` : ""}`}>
            A PDF page is displayed in this canvas when PDF.js rendering succeeds.
          </canvas>
          <div
            ref={textLayerRef}
            className="textLayer reader-text-layer"
            data-page-number={state.pageNumber}
            aria-label={`Selectable text for PDF page ${state.pageNumber}`}
          />
        </div>

        {state.mode === "loading" ? (
          <div className="reader-render-state" role="status">
            <LoaderCircle className="loading-icon" size={22} aria-hidden="true" />
            <div><h2>Loading PDF.js Reader</h2><p>Loading the managed PDF through the local same-origin endpoint.</p></div>
          </div>
        ) : null}

        {state.mode === "ready" && state.rendering ? <div className="reader-render-progress" role="status">Rendering page {state.pageNumber}…</div> : null}

        {state.mode === "empty" || state.mode === "error" ? (
          <div className="reader-render-state" role="alert">
            <AlertCircle size={22} aria-hidden="true" />
            <div>
              <h2>{state.errorKind === "unavailable" ? "Local PDF service unavailable" : state.errorKind === "not-found" ? "Managed PDF missing" : "PDF.js Reader unavailable"}</h2>
              <p>{state.message || "The managed PDF could not be displayed."}</p>
              <div className="reader-error-actions">
                <button className="reader-control" type="button" onClick={() => void controllerRef.current?.retry()}>Retry PDF.js</button>
                <button className="reader-control reader-control--secondary" type="button" onClick={() => void controllerRef.current?.activateFallback()}>Use native viewer fallback</button>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {diagnosticsEnabled ? <ReaderDiagnostics diagnostics={diagnostics} /> : null}
    </div>
  );
}
