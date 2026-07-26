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

export function isBlueprintReaderPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "reader";
}

export function isBlueprintMetadataPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "metadata";
}

export function isBlueprintReadingNotePath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "reading-note";
}

function hasSafeSegments(parts) {
  return Array.isArray(parts) && parts.every((part) => (
    typeof part === "string"
    && part.length > 0
    && part !== "."
    && part !== ".."
    && !part.includes("/")
    && !part.includes("\\")
    && !part.includes("%")
  ));
}

export function isAllowedBlueprintPath(parts) {
  if (!hasSafeSegments(parts)) return false;
  const path = parts.join("/");
  return path === "health" || path === "library/status" || path === "papers" || (parts.length === 2 && parts[0] === "papers") || isBlueprintPdfPath(parts) || isBlueprintReaderPath(parts);
}

export function isAllowedBlueprintRequest(method, parts) {
  const normalizedMethod = String(method || "").toUpperCase();
  if (!hasSafeSegments(parts)) return false;
  if (normalizedMethod === "GET") return isAllowedBlueprintPath(parts);
  if (normalizedMethod === "PATCH") return isBlueprintMetadataPath(parts);
  if (normalizedMethod === "PUT") return isBlueprintReadingNotePath(parts);
  return false;
}

export function buildBlueprintTarget(requestUrl, parts, apiUrl) {
  const incoming = new URL(requestUrl);
  const baseUrl = apiUrl.replace(/\/$/, "");
  return `${baseUrl}/${parts.map(encodeURIComponent).join("/")}${incoming.search}`;
}

export async function proxyBlueprintRequest(request, parts, { apiUrl, fetchImpl = fetch }) {
  if (!isAllowedBlueprintRequest(request.method, parts)) {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }

  const target = buildBlueprintTarget(request.url, parts, apiUrl);
  const pdfRequest = request.method === "GET" && isBlueprintPdfPath(parts);
  const commandRequest = request.method === "PATCH" || request.method === "PUT";
  const requestHeaders = new Headers({ Accept: pdfRequest ? "application/pdf" : "application/json" });
  const range = request.headers.get("Range");
  if (pdfRequest && range) requestHeaders.set("Range", range);
  let body;
  if (commandRequest) {
    const contentType = request.headers.get("Content-Type") || "";
    if (!/^application\/json(?:\s*;|$)/i.test(contentType)) {
      return Response.json({ detail: "Content-Type must be application/json." }, { status: 415 });
    }
    requestHeaders.set("Content-Type", contentType);
    try {
      body = await request.text();
    } catch {
      return Response.json({ detail: GENERIC_UNAVAILABLE_DETAIL }, { status: 503 });
    }
  }
  try {
    const upstream = await fetchImpl(target, {
      method: request.method,
      headers: requestHeaders,
      body,
      cache: "no-store",
    });
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

export async function proxyBlueprintGet(request, parts, options) {
  return proxyBlueprintRequest(request, parts, options);
}
