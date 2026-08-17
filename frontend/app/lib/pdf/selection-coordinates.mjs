const COORDINATE_SPACE = "page-normalized";

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function clampUnit(value) {
  return Math.min(1, Math.max(0, value));
}

function stableCoordinate(value) {
  return Number(clampUnit(value).toFixed(6));
}

export function normalizePageSelection({ pageNumber, text, pageRect, selectionRects }) {
  const canonicalPageNumber = Math.trunc(Number(pageNumber));
  const normalizedText = String(text || "").trim();
  const pageLeft = finiteNumber(pageRect?.left);
  const pageTop = finiteNumber(pageRect?.top);
  const pageWidth = finiteNumber(pageRect?.width);
  const pageHeight = finiteNumber(pageRect?.height);
  if (canonicalPageNumber < 1 || !normalizedText || pageWidth <= 0 || pageHeight <= 0) return null;

  const rectangles = Array.from(selectionRects || []).flatMap((rect) => {
    const left = Math.max(pageLeft, finiteNumber(rect?.left));
    const top = Math.max(pageTop, finiteNumber(rect?.top));
    const right = Math.min(pageLeft + pageWidth, finiteNumber(rect?.right));
    const bottom = Math.min(pageTop + pageHeight, finiteNumber(rect?.bottom));
    if (right <= left || bottom <= top) return [];
    return [{
      x: stableCoordinate((left - pageLeft) / pageWidth),
      y: stableCoordinate((top - pageTop) / pageHeight),
      width: stableCoordinate((right - left) / pageWidth),
      height: stableCoordinate((bottom - top) / pageHeight),
    }];
  });
  if (rectangles.length === 0) return null;

  return {
    pageNumber: canonicalPageNumber,
    text: normalizedText,
    coordinateSpace: COORDINATE_SPACE,
    rectangles,
  };
}

export function readPageSelection({ pageNumber, pageElement, selection = globalThis.getSelection?.() }) {
  if (!pageElement || !selection || selection.rangeCount < 1 || selection.isCollapsed) return null;
  if (!pageElement.contains(selection.anchorNode) || !pageElement.contains(selection.focusNode)) return null;
  const range = selection.getRangeAt(0);
  return normalizePageSelection({
    pageNumber,
    text: selection.toString(),
    pageRect: pageElement.getBoundingClientRect(),
    selectionRects: range.getClientRects(),
  });
}
