"use client";

import { AlertCircle, ChevronLeft, ChevronRight, ExternalLink, LoaderCircle, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { paperPdfUrl } from "../lib/api/client";
import { createPdfLoadingTask, createPdfTextLayer, readPdfNetworkDiagnostics, type PDFDocumentProxy } from "../lib/pdf/pdfjs-adapter";
import { DEFAULT_ZOOM, MAX_ZOOM, MIN_ZOOM, ZOOM_STEP, canvasRenderGeometry, classifyPdfError } from "../lib/pdf/reader-controller.mjs";
import { readPageSelection, type PdfPageSelection } from "../lib/pdf/selection-coordinates.mjs";

type PdfReaderUiState = {
  mode: "loading" | "ready" | "error";
  pageNumber: number;
  totalPages: number;
  zoom: number;
  rendering: boolean;
  errorKind: "not-found" | "unavailable" | "load" | "render" | null;
  message: string;
};

type PdfReaderDiagnostics = {
  documentLoadCount: number;
  renderCount: number;
  renderCancellationCount: number;
  documentLoadDurationMs: number | null;
  firstPageRenderDurationMs: number | null;
  requestCount: number | null;
  rangeRequestCount: number | null;
  fullRequestCount: number | null;
  requestMode: string;
};

const INITIAL_STATE: PdfReaderUiState = {
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

type RenderTaskLike = { promise: Promise<void>; cancel?: () => void };

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
      <div className="reader-fallback-actions"><button className="reader-control" type="button" onClick={onRetry}>Retry PDF.js Reader</button></div>
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

function ContinuousPdfPage({
  document,
  pageNumber,
  zoom,
  viewportRoot,
  active,
  onVisible,
  onRendered,
  onRenderError,
  onSelectionChange,
}: {
  document: PDFDocumentProxy;
  pageNumber: number;
  zoom: number;
  viewportRoot: HTMLElement | null;
  active: boolean;
  onVisible: (page: number) => void;
  onRendered: (page: number, durationMs: number) => void;
  onRenderError: (error: unknown) => void;
  onSelectionChange?: (selection: PdfPageSelection | null) => void;
}) {
  const pageSurfaceRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textLayerRef = useRef<HTMLDivElement | null>(null);
  const [revealed, setRevealed] = useState(false);
  const shouldRender = pageNumber === 1 || active || revealed;

  useEffect(() => {
    const element = pageSurfaceRef.current;
    if (!element || !viewportRoot || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (!entry?.isIntersecting) return;
      setRevealed(true);
      if (entry.intersectionRatio >= 0.55) onVisible(pageNumber);
    }, { root: viewportRoot, rootMargin: "240px 0px", threshold: [0.55] });
    observer.observe(element);
    return () => observer.disconnect();
  }, [onVisible, pageNumber, viewportRoot]);

  useEffect(() => {
    if (!shouldRender) return;
    let cancelled = false;
    let page: Awaited<ReturnType<PDFDocumentProxy["getPage"]>> | null = null;
    let renderTask: RenderTaskLike | null = null;
    let textLayer: Awaited<ReturnType<typeof createPdfTextLayer>> | null = null;
    const startedAt = performance.now();
    const render = async () => {
      try {
        page = await document.getPage(pageNumber);
        if (cancelled) return;
        const canvas = canvasRef.current;
        const textLayerContainer = textLayerRef.current;
        const canvasContext = canvas?.getContext("2d", { alpha: false });
        if (!canvas || !canvasContext || !textLayerContainer) throw new Error("Canvas context unavailable");
        const pageViewport = page.getViewport({ scale: zoom });
        const geometry = canvasRenderGeometry(pageViewport, window.devicePixelRatio || 1);
        canvas.width = geometry.canvasWidth;
        canvas.height = geometry.canvasHeight;
        canvas.style.width = `${geometry.cssWidth}px`;
        canvas.style.height = `${geometry.cssHeight}px`;
        textLayerContainer.replaceChildren();
        textLayerContainer.style.setProperty("--total-scale-factor", String(pageViewport.scale));
        textLayerContainer.style.setProperty("--scale-round-x", "1px");
        textLayerContainer.style.setProperty("--scale-round-y", "1px");
        renderTask = page.render({ canvas, canvasContext, viewport: pageViewport, ...(geometry.transform ? { transform: geometry.transform } : {}) }) as RenderTaskLike;
        textLayer = await createPdfTextLayer({ page, container: textLayerContainer, viewport: pageViewport });
        await Promise.all([renderTask.promise, textLayer.render()]);
        if (!cancelled) onRendered(pageNumber, Math.max(0, performance.now() - startedAt));
      } catch (error) {
        if (!cancelled && (error as { name?: string } | null)?.name !== "RenderingCancelledException") onRenderError(error);
      } finally {
        page?.cleanup();
      }
    };
    void render();
    return () => {
      cancelled = true;
      textLayer?.cancel();
      renderTask?.cancel?.();
    };
  }, [document, onRenderError, onRendered, pageNumber, shouldRender, zoom]);

  const publishSelection = () => {
    if (!onSelectionChange || !pageSurfaceRef.current) return;
    onSelectionChange(readPageSelection({ pageNumber, pageElement: pageSurfaceRef.current }));
  };

  return (
    <div id={`pdf-page-${pageNumber}`} ref={pageSurfaceRef} className="reader-page-surface reader-page-surface--continuous" data-page-number={pageNumber} onMouseUp={publishSelection} onKeyUp={publishSelection}>
      <canvas ref={canvasRef} className="reader-canvas" role="img" aria-label={`PDF page ${pageNumber}`}>A PDF page is displayed in this canvas when PDF.js rendering succeeds.</canvas>
      <div ref={textLayerRef} className="textLayer reader-text-layer" data-page-number={pageNumber} aria-label={`Selectable text for PDF page ${pageNumber}`} />
    </div>
  );
}

export function PdfJsReader({ paperId, onSelectionChange }: { paperId: string; onSelectionChange?: (selection: PdfPageSelection | null) => void }) {
  const pdfUrl = useMemo(() => paperPdfUrl(paperId), [paperId]);
  const [state, setState] = useState<PdfReaderUiState>(INITIAL_STATE);
  const [diagnostics, setDiagnostics] = useState<PdfReaderDiagnostics>(INITIAL_DIAGNOSTICS);
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy | null>(null);
  const [pageInput, setPageInput] = useState("1");
  const [viewportRoot, setViewportRoot] = useState<HTMLDivElement | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [fallbackActive, setFallbackActive] = useState(false);
  const diagnosticsEnabled = process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_BLUEPRINT_READER_DIAGNOSTICS === "1";

  useEffect(() => {
    if (fallbackActive) return;
    let current = true;
    let loadingTask: Awaited<ReturnType<typeof createPdfLoadingTask>> | null = null;
    let document: PDFDocumentProxy | null = null;
    const startedAt = performance.now();
    setPdfDocument(null);
    setState({ ...INITIAL_STATE, mode: "loading" });
    setDiagnostics((value) => ({ ...INITIAL_DIAGNOSTICS, documentLoadCount: value.documentLoadCount + 1 }));
    const load = async () => {
      try {
        loadingTask = await createPdfLoadingTask(pdfUrl);
        document = await loadingTask.promise;
        if (!current) return;
        const network = readPdfNetworkDiagnostics(pdfUrl);
        setPdfDocument(document);
        setState({ mode: "ready", pageNumber: 1, totalPages: Math.max(1, Number(document.numPages) || 1), zoom: DEFAULT_ZOOM, rendering: true, errorKind: null, message: "" });
        setDiagnostics((value) => ({ ...value, documentLoadDurationMs: Math.max(0, performance.now() - startedAt), requestCount: network.requestCount, rangeRequestCount: network.rangeRequestCount, fullRequestCount: network.fullRequestCount, requestMode: network.requestMode }));
      } catch (error) {
        if (!current) return;
        setState((value) => ({ ...value, mode: "error", rendering: false, ...classifyPdfError(error, "load") }));
      }
    };
    void load();
    return () => {
      current = false;
      void loadingTask?.destroy();
      void document?.destroy();
    };
  }, [fallbackActive, loadAttempt, pdfUrl]);

  useEffect(() => setPageInput(String(state.pageNumber)), [state.pageNumber]);

  const setPage = (requestedPage: number) => {
    if (state.mode !== "ready") return;
    const pageNumber = Math.min(state.totalPages, Math.max(1, Math.trunc(requestedPage)));
    setState((current) => ({ ...current, pageNumber, rendering: true }));
    window.requestAnimationFrame(() => {
      const target = document.getElementById(`pdf-page-${pageNumber}`);
      if (!target || !viewportRoot) return;
      viewportRoot.scrollTo({ top: target.offsetTop - viewportRoot.offsetTop, behavior: "smooth" });
    });
  };
  const commitPageInput = () => {
    const requestedPage = Number.parseInt(pageInput, 10);
    if (!Number.isFinite(requestedPage)) return setPageInput(String(state.pageNumber));
    setPage(requestedPage);
  };
  const setZoom = (requestedZoom: number) => {
    const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, requestedZoom));
    setState((current) => ({ ...current, zoom, rendering: true }));
  };
  const onVisible = useCallback((pageNumber: number) => setState((current) => current.mode === "ready" && current.pageNumber !== pageNumber ? { ...current, pageNumber } : current), []);
  const onRendered = useCallback((pageNumber: number, durationMs: number) => {
    setState((current) => current.pageNumber === pageNumber ? { ...current, rendering: false } : current);
    setDiagnostics((current) => ({ ...current, renderCount: current.renderCount + 1, firstPageRenderDurationMs: current.firstPageRenderDurationMs ?? durationMs }));
  }, []);
  const onRenderError = useCallback((error: unknown) => setState((current) => ({ ...current, mode: "error", rendering: false, ...classifyPdfError(error, "render") })), []);

  if (fallbackActive) return <NativePdfFallback pdfUrl={pdfUrl} onRetry={() => { setFallbackActive(false); setLoadAttempt((value) => value + 1); }} />;

  const controlsReady = state.mode === "ready";
  return (
    <div className="pdfjs-reader">
      <div className="reader-toolbar" role="toolbar" aria-label="PDF page and zoom controls">
        <div className="reader-toolbar__group" aria-label="Page navigation">
          <button className="reader-control" type="button" aria-label="Previous PDF page" disabled={!controlsReady || state.pageNumber <= 1} onClick={() => setPage(state.pageNumber - 1)}><ChevronLeft size={16} />Previous</button>
          <label className="reader-page-field"><span>Page</span><input aria-label="PDF page number" type="number" inputMode="numeric" min={1} max={Math.max(1, state.totalPages)} value={pageInput} disabled={!controlsReady} onChange={(event) => setPageInput(event.target.value)} onBlur={commitPageInput} onKeyDown={(event) => { if (event.key === "Enter") commitPageInput(); }} /><span aria-live="polite">of {state.totalPages || "?"}</span></label>
          <button className="reader-control" type="button" aria-label="Next PDF page" disabled={!controlsReady || state.pageNumber >= state.totalPages} onClick={() => setPage(state.pageNumber + 1)}>Next<ChevronRight size={16} /></button>
        </div>
        <div className="reader-toolbar__group" aria-label="PDF zoom controls">
          <button className="reader-control" type="button" aria-label="Zoom out" disabled={!controlsReady || state.zoom <= MIN_ZOOM} onClick={() => setZoom(state.zoom - ZOOM_STEP)}><ZoomOut size={16} />Zoom out</button>
          <output className="reader-zoom-value" aria-live="polite">{Math.round(state.zoom * 100)}%</output>
          <button className="reader-control" type="button" aria-label="Zoom in" disabled={!controlsReady || state.zoom >= MAX_ZOOM} onClick={() => setZoom(state.zoom + ZOOM_STEP)}><ZoomIn size={16} />Zoom in</button>
          <button className="reader-control" type="button" aria-label="Reset PDF zoom" disabled={!controlsReady || state.zoom === DEFAULT_ZOOM} onClick={() => setZoom(DEFAULT_ZOOM)}><RotateCcw size={16} />Reset</button>
        </div>
      </div>
      <div ref={setViewportRoot} className="reader-canvas-viewport">
        {pdfDocument ? <div className="reader-pdf-page-stack">{Array.from({ length: state.totalPages }, (_, index) => index + 1).map((pageNumber) => <ContinuousPdfPage key={`${pageNumber}:${state.zoom}`} document={pdfDocument} pageNumber={pageNumber} zoom={state.zoom} viewportRoot={viewportRoot} active={state.pageNumber === pageNumber} onVisible={onVisible} onRendered={onRendered} onRenderError={onRenderError} onSelectionChange={onSelectionChange} />)}</div> : null}
        {state.mode === "loading" ? <div className="reader-render-state" role="status"><LoaderCircle className="loading-icon" size={22} aria-hidden="true" /><div><h2>Loading PDF.js Reader</h2><p>Loading the managed PDF through the local same-origin endpoint.</p></div></div> : null}
        {state.mode === "ready" && state.rendering ? <div className="reader-render-progress" role="status">Rendering page {state.pageNumber}…</div> : null}
        {state.mode === "error" ? <div className="reader-render-state" role="alert"><AlertCircle size={22} aria-hidden="true" /><div><h2>{state.errorKind === "unavailable" ? "Local PDF service unavailable" : state.errorKind === "not-found" ? "Managed PDF missing" : "PDF.js Reader unavailable"}</h2><p>{state.message || "The managed PDF could not be displayed."}</p><div className="reader-error-actions"><button className="reader-control" type="button" onClick={() => setLoadAttempt((value) => value + 1)}>Retry PDF.js</button><button className="reader-control reader-control--secondary" type="button" onClick={() => setFallbackActive(true)}>Use native viewer fallback</button></div></div></div> : null}
      </div>
      {diagnosticsEnabled ? <ReaderDiagnostics diagnostics={diagnostics} /> : null}
    </div>
  );
}
