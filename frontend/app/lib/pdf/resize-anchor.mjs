function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function createPdfViewportAnchor({ pageNumber, pageTop, pageHeight, viewportTop, viewportHeight }) {
  const safePageHeight = Math.max(1, Number(pageHeight) || 1);
  const safeViewportHeight = Math.max(0, Number(viewportHeight) || 0);
  const viewportAnchorOffset = safeViewportHeight / 2;
  const relativePageOffset = clamp(
    ((Number(viewportTop) || 0) + viewportAnchorOffset - (Number(pageTop) || 0)) / safePageHeight,
    0,
    1,
  );

  return {
    pageNumber: Math.max(1, Math.trunc(Number(pageNumber) || 1)),
    relativePageOffset,
    viewportAnchorOffset,
  };
}

export function scrollTopForPdfViewportAnchor({ pageTop, pageHeight, relativePageOffset, viewportAnchorOffset }) {
  const safePageHeight = Math.max(1, Number(pageHeight) || 1);
  return Math.max(
    0,
    (Number(pageTop) || 0)
      + safePageHeight * clamp(Number(relativePageOffset) || 0, 0, 1)
      - Math.max(0, Number(viewportAnchorOffset) || 0),
  );
}
