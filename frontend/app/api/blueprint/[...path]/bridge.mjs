const GENERIC_UNAVAILABLE_DETAIL = "Local BluePrintReboot API is unavailable.";
const SAFE_PDF_RESPONSE_HEADERS = [
  "Content-Type",
  "Content-Length",
  "Content-Range",
  "Accept-Ranges",
  "ETag",
  "Last-Modified",
  "Content-Disposition",
];

export function isBlueprintPdfPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "pdf";
}

export function isAllowedBlueprintPath(parts) {
  if (!Array.isArray(parts) || !parts.every((part) => typeof part === "string" && part.length > 0)) return false;
  const path = parts.join("/");
  return path === "health" || path === "library/status" || path === "papers" || (parts.length === 2 && parts[0] === "papers") || isBlueprintPdfPath(parts);
}

export function buildBlueprintTarget(requestUrl, parts, apiUrl) {
  const incoming = new URL(requestUrl);
  const baseUrl = apiUrl.replace(/\/$/, "");
  return `${baseUrl}/${parts.map(encodeURIComponent).join("/")}${incoming.search}`;
}

export async function proxyBlueprintGet(request, parts, { apiUrl, fetchImpl = fetch }) {
  if (!isAllowedBlueprintPath(parts)) return Response.json({ detail: "Not found." }, { status: 404 });

  const target = buildBlueprintTarget(request.url, parts, apiUrl);
  const pdfRequest = isBlueprintPdfPath(parts);
  const requestHeaders = new Headers({ Accept: pdfRequest ? "application/pdf" : "application/json" });
  const range = request.headers.get("Range");
  if (pdfRequest && range) requestHeaders.set("Range", range);
  try {
    const upstream = await fetchImpl(target, { headers: requestHeaders, cache: "no-store" });
    if (upstream.status >= 500) return Response.json({ detail: GENERIC_UNAVAILABLE_DETAIL }, { status: 503 });
    const responseHeaders = new Headers();
    const allowedHeaders = pdfRequest ? SAFE_PDF_RESPONSE_HEADERS : ["Content-Type"];
    for (const name of allowedHeaders) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    if (!responseHeaders.has("Content-Type")) responseHeaders.set("Content-Type", pdfRequest ? "application/pdf" : "application/json");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json({ detail: GENERIC_UNAVAILABLE_DETAIL }, { status: 503 });
  }
}
