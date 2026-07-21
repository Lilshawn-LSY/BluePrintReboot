export const DEFAULT_ZOOM = 1;
export const MIN_ZOOM = 0.5;
export const MAX_ZOOM = 3;
export const ZOOM_STEP = 0.25;

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function safeStatus(error) {
  if (!error || typeof error !== "object") return undefined;
  const status = Number(error.status);
  return Number.isInteger(status) ? status : undefined;
}

export function isPdfCancellation(error) {
  return Boolean(
    error
      && typeof error === "object"
      && (error.name === "RenderingCancelledException" || error.name === "AbortException"),
  );
}

export function classifyPdfError(error, phase = "load") {
  const status = safeStatus(error);
  if (status === 404) {
    return { errorKind: "not-found", message: "The managed PDF is missing." };
  }
  if (status === 503 || (error && typeof error === "object" && error.name === "ResponseException")) {
    return {
      errorKind: "unavailable",
      message: "The local PDF service is unavailable. Start the local API and retry.",
    };
  }
  if (phase === "render") {
    return {
      errorKind: "render",
      message: "PDF.js could not render this page. Retry or use the native browser fallback.",
    };
  }
  return {
    errorKind: "load",
    message: "PDF.js could not load this managed PDF. Retry or use the native browser fallback.",
  };
}

function initialState() {
  return {
    mode: "idle",
    pageNumber: 1,
    totalPages: 0,
    zoom: DEFAULT_ZOOM,
    rendering: false,
    errorKind: null,
    message: "",
  };
}

function initialDiagnostics() {
  return {
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
}

async function safeCall(callback) {
  try {
    await callback?.();
  } catch {
    // Cleanup is best-effort and deliberately never hides the originating load/render error.
  }
}

export class PdfReaderController {
  constructor({
    createLoadingTask,
    getCanvas,
    onState = () => {},
    onDiagnostics = () => {},
    getNetworkDiagnostics = () => ({}),
    now = () => performance.now(),
  }) {
    this.createLoadingTask = createLoadingTask;
    this.getCanvas = getCanvas;
    this.onState = onState;
    this.onDiagnostics = onDiagnostics;
    this.getNetworkDiagnostics = getNetworkDiagnostics;
    this.now = now;

    this.state = initialState();
    this.diagnostics = initialDiagnostics();
    this.url = "";
    this.loadingTask = null;
    this.document = null;
    this.renderTask = null;
    this.activePage = null;
    this.loadCycle = 0;
    this.renderCycle = 0;
    this.destroyed = false;
  }

  snapshot() {
    return { ...this.state };
  }

  diagnosticsSnapshot() {
    return { ...this.diagnostics };
  }

  _emitState(nextState) {
    this.state = { ...this.state, ...nextState };
    this.onState(this.snapshot());
  }

  _emitDiagnostics(nextDiagnostics = {}) {
    this.diagnostics = { ...this.diagnostics, ...nextDiagnostics };
    this.onDiagnostics(this.diagnosticsSnapshot());
  }

  async load(url) {
    const cycle = ++this.loadCycle;
    this.destroyed = false;
    this.url = url;
    this._emitState({
      mode: url ? "loading" : "empty",
      pageNumber: 1,
      totalPages: 0,
      zoom: DEFAULT_ZOOM,
      rendering: false,
      errorKind: null,
      message: url ? "" : "No managed PDF URL is available.",
    });
    await this._disposePdfResources();
    if (!url || cycle !== this.loadCycle || this.destroyed) return;

    const loadStartedAt = this.now();
    this._emitDiagnostics({
      documentLoadCount: this.diagnostics.documentLoadCount + 1,
      documentLoadDurationMs: null,
      firstPageRenderDurationMs: null,
      requestCount: null,
      rangeRequestCount: null,
      fullRequestCount: null,
      requestMode: "pdfjs-auto",
    });

    try {
      const loadingTask = await this.createLoadingTask(url);
      if (cycle !== this.loadCycle || this.destroyed) {
        await safeCall(() => loadingTask.destroy());
        return;
      }
      this.loadingTask = loadingTask;
      const document = await loadingTask.promise;
      if (cycle !== this.loadCycle || this.destroyed) {
        await safeCall(() => document.cleanup?.());
        await safeCall(() => loadingTask.destroy());
        return;
      }

      this.document = document;
      const totalPages = Math.max(1, Number(document.numPages) || 1);
      this._emitDiagnostics({ documentLoadDurationMs: Math.max(0, this.now() - loadStartedAt) });
      this._emitState({
        mode: "ready",
        pageNumber: 1,
        totalPages,
        zoom: DEFAULT_ZOOM,
        rendering: true,
        errorKind: null,
        message: "",
      });
      await this._renderCurrentPage({ firstPage: true });
    } catch (error) {
      if (cycle !== this.loadCycle || this.destroyed || isPdfCancellation(error)) return;
      await this._disposePdfResources();
      this._emitState({
        mode: "error",
        rendering: false,
        ...classifyPdfError(error, "load"),
      });
    }
  }

  retry() {
    return this.load(this.url);
  }

  setPage(requestedPage) {
    if (!this.document || this.state.mode !== "ready") return Promise.resolve();
    const numericPage = Number(requestedPage);
    if (!Number.isFinite(numericPage)) return Promise.resolve();
    const pageNumber = clamp(Math.trunc(numericPage), 1, this.state.totalPages);
    if (pageNumber === this.state.pageNumber && !this.state.rendering) return Promise.resolve();
    this._emitState({ pageNumber, rendering: true, errorKind: null, message: "" });
    return this._renderCurrentPage();
  }

  previousPage() {
    return this.setPage(this.state.pageNumber - 1);
  }

  nextPage() {
    return this.setPage(this.state.pageNumber + 1);
  }

  setZoom(requestedZoom) {
    if (!this.document || this.state.mode !== "ready") return Promise.resolve();
    const numericZoom = Number(requestedZoom);
    if (!Number.isFinite(numericZoom)) return Promise.resolve();
    const zoom = clamp(numericZoom, MIN_ZOOM, MAX_ZOOM);
    if (zoom === this.state.zoom && !this.state.rendering) return Promise.resolve();
    this._emitState({ zoom, rendering: true, errorKind: null, message: "" });
    return this._renderCurrentPage();
  }

  zoomIn() {
    return this.setZoom(this.state.zoom + ZOOM_STEP);
  }

  zoomOut() {
    return this.setZoom(this.state.zoom - ZOOM_STEP);
  }

  resetZoom() {
    return this.setZoom(DEFAULT_ZOOM);
  }

  async activateFallback() {
    ++this.loadCycle;
    await this._disposePdfResources();
    if (this.destroyed) return;
    this._emitState({
      mode: "fallback",
      rendering: false,
      errorKind: null,
      message: "Native browser fallback is active.",
    });
  }

  async destroy() {
    this.destroyed = true;
    ++this.loadCycle;
    await this._disposePdfResources();
  }

  async _renderCurrentPage({ firstPage = false } = {}) {
    const document = this.document;
    if (!document) return;
    const cycle = ++this.renderCycle;
    await this._cancelActiveRender();
    if (cycle !== this.renderCycle || document !== this.document || this.destroyed) return;

    const pageNumber = this.state.pageNumber;
    const zoom = this.state.zoom;
    const renderStartedAt = this.now();
    let page = null;
    let renderTask = null;

    try {
      page = await document.getPage(pageNumber);
      if (cycle !== this.renderCycle || document !== this.document || this.destroyed) {
        await safeCall(() => page.cleanup?.());
        return;
      }

      const canvas = this.getCanvas();
      const canvasContext = canvas?.getContext?.("2d", { alpha: false });
      if (!canvas || !canvasContext) throw new Error("Canvas context unavailable");
      const viewport = page.getViewport({ scale: zoom });
      canvas.width = Math.max(1, Math.ceil(viewport.width));
      canvas.height = Math.max(1, Math.ceil(viewport.height));

      renderTask = page.render({ canvasContext, viewport });
      if (cycle !== this.renderCycle || document !== this.document || this.destroyed) {
        renderTask.cancel?.();
        await safeCall(() => renderTask.promise);
        await safeCall(() => page.cleanup?.());
        return;
      }

      this.renderTask = renderTask;
      this.activePage = page;
      this._emitDiagnostics({ renderCount: this.diagnostics.renderCount + 1 });
      await renderTask.promise;
      if (cycle !== this.renderCycle || document !== this.document || this.destroyed) return;

      const renderDuration = Math.max(0, this.now() - renderStartedAt);
      const network = this.getNetworkDiagnostics(this.url) || {};
      this._emitDiagnostics({
        ...(firstPage && this.diagnostics.firstPageRenderDurationMs === null
          ? { firstPageRenderDurationMs: renderDuration }
          : {}),
        requestCount: network.requestCount ?? this.diagnostics.requestCount,
        rangeRequestCount: network.rangeRequestCount ?? this.diagnostics.rangeRequestCount,
        fullRequestCount: network.fullRequestCount ?? this.diagnostics.fullRequestCount,
        requestMode: network.requestMode ?? this.diagnostics.requestMode,
      });
      this._emitState({ mode: "ready", rendering: false, errorKind: null, message: "" });
    } catch (error) {
      if (cycle !== this.renderCycle || document !== this.document || this.destroyed || isPdfCancellation(error)) return;
      this._clearCanvas();
      this._emitState({
        mode: "error",
        rendering: false,
        ...classifyPdfError(error, "render"),
      });
    } finally {
      if (this.renderTask === renderTask) this.renderTask = null;
      if (this.activePage === page) this.activePage = null;
      await safeCall(() => page?.cleanup?.());
    }
  }

  async _cancelActiveRender() {
    const renderTask = this.renderTask;
    const page = this.activePage;
    this.renderTask = null;
    this.activePage = null;
    if (renderTask) {
      renderTask.cancel?.();
      this._emitDiagnostics({
        renderCancellationCount: this.diagnostics.renderCancellationCount + 1,
      });
      await safeCall(() => renderTask.promise);
    }
    await safeCall(() => page?.cleanup?.());
  }

  async _disposePdfResources() {
    ++this.renderCycle;
    await this._cancelActiveRender();
    const document = this.document;
    const loadingTask = this.loadingTask;
    this.document = null;
    this.loadingTask = null;
    await safeCall(() => document?.cleanup?.());
    if (loadingTask) await safeCall(() => loadingTask.destroy?.());
    else await safeCall(() => document?.destroy?.());
    this._clearCanvas();
  }

  _clearCanvas() {
    const canvas = this.getCanvas?.();
    if (!canvas) return;
    const context = canvas.getContext?.("2d");
    context?.clearRect?.(0, 0, canvas.width || 0, canvas.height || 0);
    canvas.width = 0;
    canvas.height = 0;
  }
}
