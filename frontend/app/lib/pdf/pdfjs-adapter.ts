import type { PDFDocumentLoadingTask, PDFDocumentProxy } from "pdfjs-dist";


const RANGE_CHUNK_SIZE = 64 * 1024;
let pdfJsModulePromise: Promise<typeof import("pdfjs-dist")> | null = null;


async function loadPdfJsModule(): Promise<typeof import("pdfjs-dist")> {
  if (typeof window === "undefined") {
    throw new Error("PDF.js is available only inside the browser Reader client boundary.");
  }
  if (!pdfJsModulePromise) {
    pdfJsModulePromise = Promise.all([
      import("pdfjs-dist"),
      import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
    ]).then(([pdfjs, worker]) => {
      pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
      return pdfjs;
    });
  }
  return pdfJsModulePromise;
}


export async function createPdfLoadingTask(url: string): Promise<PDFDocumentLoadingTask> {
  const pdfjs = await loadPdfJsModule();
  return pdfjs.getDocument({
    url,
    rangeChunkSize: RANGE_CHUNK_SIZE,
    disableRange: false,
    disableStream: false,
    disableAutoFetch: false,
  });
}


type ResponseAwareResourceTiming = PerformanceResourceTiming & { responseStatus?: number };


export function readPdfNetworkDiagnostics(url: string): {
  requestCount: number;
  rangeRequestCount: number;
  fullRequestCount: number;
  requestMode: string;
} {
  if (typeof performance === "undefined" || typeof performance.getEntriesByName !== "function") {
    return { requestCount: 0, rangeRequestCount: 0, fullRequestCount: 0, requestMode: "unavailable" };
  }
  const entries = performance
    .getEntriesByName(url, "resource")
    .filter((entry): entry is ResponseAwareResourceTiming => entry.entryType === "resource");
  const rangeRequestCount = entries.filter((entry) => entry.responseStatus === 206).length;
  const fullRequestCount = entries.filter((entry) => entry.responseStatus === 200).length;
  const requestMode = rangeRequestCount > 0
    ? "range"
    : fullRequestCount > 0
      ? "full"
      : entries.length > 0
        ? "status-unavailable"
        : "not-observed";
  return { requestCount: entries.length, rangeRequestCount, fullRequestCount, requestMode };
}


export type { PDFDocumentProxy };
