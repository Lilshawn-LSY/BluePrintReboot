export type PdfReaderMode = "idle" | "empty" | "loading" | "ready" | "error" | "fallback";
export type PdfErrorKind = "not-found" | "unavailable" | "load" | "render" | null;

export interface PdfReaderState {
  mode: PdfReaderMode;
  pageNumber: number;
  totalPages: number;
  zoom: number;
  rendering: boolean;
  errorKind: PdfErrorKind;
  message: string;
}

export interface PdfReaderDiagnostics {
  documentLoadCount: number;
  renderCount: number;
  renderCancellationCount: number;
  documentLoadDurationMs: number | null;
  firstPageRenderDurationMs: number | null;
  requestCount: number | null;
  rangeRequestCount: number | null;
  fullRequestCount: number | null;
  requestMode: string;
}

export interface PdfLoadingTaskLike {
  promise: Promise<unknown>;
  destroy?: () => Promise<void> | void;
}

export const DEFAULT_ZOOM: number;
export const MIN_ZOOM: number;
export const MAX_ZOOM: number;
export const ZOOM_STEP: number;
export function isPdfCancellation(error: unknown): boolean;
export function classifyPdfError(error: unknown, phase?: "load" | "render"): Pick<PdfReaderState, "errorKind" | "message">;

export class PdfReaderController {
  constructor(options: {
    createLoadingTask: (url: string) => Promise<PdfLoadingTaskLike>;
    getCanvas: () => HTMLCanvasElement | null;
    onState?: (state: PdfReaderState) => void;
    onDiagnostics?: (diagnostics: PdfReaderDiagnostics) => void;
    getNetworkDiagnostics?: (url: string) => Partial<PdfReaderDiagnostics>;
    now?: () => number;
  });
  snapshot(): PdfReaderState;
  diagnosticsSnapshot(): PdfReaderDiagnostics;
  load(url: string): Promise<void>;
  retry(): Promise<void>;
  setPage(pageNumber: number): Promise<void>;
  previousPage(): Promise<void>;
  nextPage(): Promise<void>;
  setZoom(zoom: number): Promise<void>;
  zoomIn(): Promise<void>;
  zoomOut(): Promise<void>;
  resetZoom(): Promise<void>;
  activateFallback(): Promise<void>;
  destroy(): Promise<void>;
}
