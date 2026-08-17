export interface NormalizedPageRectangle {
  /** Top-left page-relative X coordinate in the inclusive range 0..1. */
  x: number;
  /** Top-left page-relative Y coordinate in the inclusive range 0..1. */
  y: number;
  width: number;
  height: number;
}

export interface PdfPageSelection {
  /** Canonical BluePrint page number. Always 1-based. */
  pageNumber: number;
  text: string;
  /** Geometry is normalized against the rotated logical PDF.js viewport. */
  coordinateSpace: "page-normalized";
  rectangles: NormalizedPageRectangle[];
}

export function normalizePageSelection(options: {
  pageNumber: number;
  text: string;
  pageRect: DOMRect | DOMRectReadOnly;
  selectionRects: Iterable<DOMRect | DOMRectReadOnly>;
}): PdfPageSelection | null;

export function readPageSelection(options: {
  pageNumber: number;
  pageElement: HTMLElement;
  selection?: Selection | null;
}): PdfPageSelection | null;
