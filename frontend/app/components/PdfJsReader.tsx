"use client";

import { AlertCircle, ChevronLeft, ChevronRight, ExternalLink, LoaderCircle, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { paperPdfUrl } from "../lib/api/client";
import { createPdfLoadingTask, createPdfTextLayer, readPdfNetworkDiagnostics, type PDFDocumentProxy } from "../lib/pdf/pdfjs-adapter";
import { DEFAULT_ZOOM, MAX_ZOOM, MIN_ZOOM, ZOOM_STEP, canvasRenderGeometry, classifyPdfError, fitPageZoom, fitWidthZoom } from "../lib/pdf/reader-controller.mjs";
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
type PdfViewMode = "fit-width" | "fit-page" | "manual";

const PDF_VIEW_PREFERENCE_KEY = "blueprint-reboot:pdf-view-preference";
const PDF_VIEWPORT_PADDING = 48;

function readPdfViewPreference(): { mode: PdfViewMode; zoom: number } {
  if (typeof window === "undefined") return { mode: "fit-width", zoom: DEFAULT_ZOOM };
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(PDF_VIEW_PREFERENCE_KEY) || "");
    if (!parsed || !["fit-width", "fit-page", "manual"].includes(parsed.mode)) return { mode: "fit-width", zoom: DEFAULT_ZOOM };
    const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(parsed.zoom) || DEFAULT_ZOOM));
    return { mode: parsed.mode, zoom };
  } catch {
    return { mode: "fit-width", zoom: DEFAULT_ZOOM };
  }
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
  const viewportRootRef = useRef<HTMLDivElement | null>(null);
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const viewPreferenceRef = useRef(readPdfViewPreference());
  const [viewMode, setViewMode] = useState<PdfViewMode>(() => viewPreferenceRef.current.mode);
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
        setState({ mode: "ready", pageNumber: 1, totalPages: Math.max(1, Number(document.numPages) || 1), zoom: viewPreferenceRef.current.mode === "manual" ? viewPreferenceRef.current.zoom : DEFAULT_ZOOM, rendering: true, errorKind: null, message: "" });
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

  const setViewportElement = useCallback((element: HTMLDivElement | null) => {
    viewportRootRef.current = element;
    setViewportRoot(element);
  }, []);

  useEffect(() => {
    if (!pdfDocument || state.mode !== "ready") return;
    let active = true;
    void pdfDocument.getPage(state.pageNumber).then((page) => {
      if (!active) return;
      const viewport = page.getViewport({ scale: 1 });
      setPageSize({ width: viewport.width, height: viewport.height });
    }).catch(() => { /* The normal render path owns visible error handling. */ });
    return () => { active = false; };
  }, [pdfDocument, state.mode, state.pageNumber]);

  const applyFitMode = useCallback((mode: Exclude<PdfViewMode, "manual">) => {
    const viewport = viewportRootRef.current;
    if (!viewport || !pageSize.width || !pageSize.height) return;
    const zoom = mode === "fit-width"
      ? fitWidthZoom({ availableWidth: viewport.clientWidth, pageWidth: pageSize.width, horizontalPadding: PDF_VIEWPORT_PADDING })
      : fitPageZoom({ availableWidth: viewport.clientWidth, availableHeight: viewport.clientHeight, pageWidth: pageSize.width, pageHeight: pageSize.height, horizontalPadding: PDF_VIEWPORT_PADDING, verticalPadding: PDF_VIEWPORT_PADDING });
    setState((current) => ({ ...current, zoom, rendering: true }));
  }, [pageSize]);

  useEffect(() => {
    if (!viewportRoot || !pageSize.width || viewMode === "manual") return;
    const update = () => applyFitMode(viewMode);
    update();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(update);
    observer.observe(viewportRoot);
    return () => observer.disconnect();
  }, [applyFitMode, pageSize.width, viewMode, viewportRoot]);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(PDF_VIEW_PREFERENCE_KEY, JSON.stringify({ mode: viewMode, zoom: state.zoom }));
    } catch { /* The active reader remains usable when session storage is unavailable. */ }
  }, [state.zoom, viewMode]);

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
  const setManualZoom = (requestedZoom: number) => {
    const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, requestedZoom));
    setViewMode("manual");
    setState((current) => ({ ...current, zoom, rendering: true }));
  };
  const chooseFitMode = (mode: Exclude<PdfViewMode, "manual">) => {
    setViewMode(mode);
    applyFitMode(mode);
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
          <button className={viewMode === "fit-width" ? "reader-control reader-control--active" : "reader-control reader-control--secondary"} type="button" title="Fit PDF to available width" aria-label="Fit PDF to available width" aria-pressed={viewMode === "fit-width"} disabled={!controlsReady} onClick={() => chooseFitMode("fit-width")}>Fit width</button>
          <button className={viewMode === "fit-page" ? "reader-control reader-control--active" : "reader-control reader-control--secondary"} type="button" title="Fit PDF page to available space" aria-label="Fit PDF page to available space" aria-pressed={viewMode === "fit-page"} disabled={!controlsReady} onClick={() => chooseFitMode("fit-page")}>Fit page</button>
          <button className="reader-control" type="button" aria-label="Zoom out" title="Zoom out" disabled={!controlsReady || state.zoom <= MIN_ZOOM} onClick={() => setManualZoom(state.zoom - ZOOM_STEP)}><ZoomOut size={16} /><span className="sr-only">Zoom out</span></button>
          <output className="reader-zoom-value" aria-live="polite">{Math.round(state.zoom * 100)}% <span className="sr-only">{viewMode === "manual" ? "manual zoom" : viewMode.replace("-", " ")}</span></output>
          <button className="reader-control" type="button" aria-label="Zoom in" title="Zoom in" disabled={!controlsReady || state.zoom >= MAX_ZOOM} onClick={() => setManualZoom(state.zoom + ZOOM_STEP)}><ZoomIn size={16} /><span className="sr-only">Zoom in</span></button>
          <button className="reader-control reader-control--secondary" type="button" aria-label="Set manual zoom to 100 percent" title="Set manual zoom to 100 percent" disabled={!controlsReady || (viewMode === "manual" && state.zoom === DEFAULT_ZOOM)} onClick={() => setManualZoom(DEFAULT_ZOOM)}><RotateCcw size={16} /><span className="sr-only">Manual 100 percent</span></button>
        </div>
      </div>
      <div ref={setViewportElement} className="reader-canvas-viewport">
        {pdfDocument ? <div className="reader-pdf-page-stack">{Array.from({ length: state.totalPages }, (_, index) => index + 1).map((pageNumber) => <ContinuousPdfPage key={`${pageNumber}:${state.zoom}`} document={pdfDocument} pageNumber={pageNumber} zoom={state.zoom} viewportRoot={viewportRoot} active={state.pageNumber === pageNumber} onVisible={onVisible} onRendered={onRendered} onRenderError={onRenderError} onSelectionChange={onSelectionChange} />)}</div> : null}
        {state.mode === "loading" ? <div className="reader-render-state" role="status"><LoaderCircle className="loading-icon" size={22} aria-hidden="true" /><div><h2>Loading PDF.js Reader</h2><p>Loading the managed PDF through the local same-origin endpoint.</p></div></div> : null}
        {state.mode === "ready" && state.rendering ? <div className="reader-render-progress" role="status">Rendering page {state.pageNumber}…</div> : null}
        {state.mode === "error" ? <div className="reader-render-state" role="alert"><AlertCircle size={22} aria-hidden="true" /><div><h2>{state.errorKind === "unavailable" ? "Local PDF service unavailable" : state.errorKind === "not-found" ? "Managed PDF missing" : "PDF.js Reader unavailable"}</h2><p>{state.message || "The managed PDF could not be displayed."}</p><div className="reader-error-actions"><button className="reader-control" type="button" onClick={() => setLoadAttempt((value) => value + 1)}>Retry PDF.js</button><button className="reader-control reader-control--secondary" type="button" onClick={() => setFallbackActive(true)}>Use native viewer fallback</button></div></div></div> : null}
      </div>
      {diagnosticsEnabled ? <ReaderDiagnostics diagnostics={diagnostics} /> : null}
    </div>
  );
}
