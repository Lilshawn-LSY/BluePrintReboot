const GENERIC_UNAVAILABLE_DETAIL = "Local BluePrintReboot API is unavailable.";
export const MAX_COMMAND_BODY_BYTES = 8 * 1024 * 1024;
export const MAX_PDF_UPLOAD_BODY_BYTES = 512 * 1024 * 1024;
export const UPSTREAM_TIMEOUT_MS = 120_000;
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

export function isBlueprintFullTextPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "full-text";
}

export function isBlueprintFullTextStatusPath(parts) {
  return Array.isArray(parts) && parts.length === 4 && parts[0] === "papers" && parts[2] === "full-text" && parts[3] === "status";
}

export function isBlueprintFullTextExtractPath(parts) {
  return Array.isArray(parts) && parts.length === 4 && parts[0] === "papers" && parts[2] === "full-text" && parts[3] === "extract";
}

export function isBlueprintMetadataPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "metadata";
}

export function isBlueprintReadingStatusPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "reading-status";
}

export function isBlueprintMetadataEnrichmentPreviewPath(parts) {
  return Array.isArray(parts) && parts.length === 4 && parts[0] === "papers" && parts[2] === "metadata" && parts[3] === "enrichment-preview";
}

export function isBlueprintPaperTagsPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "tags";
}

export function isBlueprintTagCandidatesPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "tag-candidates";
}

export function isBlueprintTagCandidateGeneratePath(parts) {
  return Array.isArray(parts) && parts.length === 4 && parts[0] === "papers" && parts[2] === "tag-candidates" && parts[3] === "generate";
}

export function isBlueprintTagCandidateActionPath(parts) {
  return Array.isArray(parts)
    && parts.length === 5
    && parts[0] === "papers"
    && parts[2] === "tag-candidates"
    && ["approve", "reject", "promote", "apply"].includes(parts[4]);
}

export function isBlueprintTagGovernancePath(parts) {
  return Array.isArray(parts) && parts.length === 2 && parts[0] === "tags" && parts[1] === "governance";
}

export function isBlueprintTagReviewQueuePath(parts) {
  return Array.isArray(parts) && parts.length === 2 && parts[0] === "tags" && parts[1] === "review-queue";
}

export function isBlueprintCanonicalTagPath(parts) {
  return Array.isArray(parts) && parts.length === 2 && parts[0] === "tags" && parts[1] !== "governance";
}

export function isBlueprintCanonicalTagAliasesPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "tags" && parts[2] === "aliases";
}

export function isBlueprintCanonicalTagDeprecatePath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "tags" && parts[2] === "deprecate";
}

export function isBlueprintReadingNotePath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "reading-note";
}

export function isBlueprintManagedPdfScanPath(parts) {
  return Array.isArray(parts) && parts.length === 2 && parts[0] === "papers" && parts[1] === "scan";
}

export function isBlueprintManagedPdfImportPath(parts) {
  return Array.isArray(parts) && parts.length === 2 && parts[0] === "papers" && parts[1] === "import";
}

export function isBlueprintManagedPdfUploadPath(parts) {
  return Array.isArray(parts) && parts.length === 2 && parts[0] === "papers" && parts[1] === "upload";
}

export function isBlueprintManagedPdfReconnectPath(parts) {
  return Array.isArray(parts) && parts.length === 2 && parts[0] === "papers" && parts[1] === "reconnect";
}

export function isBlueprintPaperRemovePdfPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "remove-pdf";
}

export function isBlueprintPaperArchivePath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "archive";
}

export function isBlueprintNoteBlocksPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "papers" && parts[2] === "note-blocks";
}

export function isBlueprintNoteBlockPath(parts) {
  return Array.isArray(parts) && parts.length === 4 && parts[0] === "papers" && parts[2] === "note-blocks";
}

export function isBlueprintProjectPath(parts) {
  return Array.isArray(parts) && parts.length === 2 && parts[0] === "projects";
}

export function isBlueprintProjectArchivePath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "projects" && parts[2] === "archive";
}

export function isBlueprintProjectPaperLinksPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "projects" && parts[2] === "paper-links";
}

export function isBlueprintProjectPaperLinkPath(parts) {
  return Array.isArray(parts) && parts.length === 4 && parts[0] === "projects" && parts[2] === "paper-links";
}

export function isBlueprintProjectNoteBlockLinksPath(parts) {
  return Array.isArray(parts) && parts.length === 3 && parts[0] === "projects" && parts[2] === "note-block-links";
}

export function isBlueprintProjectNoteBlockLinkPath(parts) {
  return Array.isArray(parts) && parts.length === 4 && parts[0] === "projects" && parts[2] === "note-block-links";
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
  return path === "health"
    || path === "library/status"
    || path === "papers"
    || path === "projects"
    || path === "tags"
    || path === "tags/summary"
    || isBlueprintTagReviewQueuePath(parts)
    || path === "tags/governance"
    || path === "settings/summary"
    || (parts.length === 2 && parts[0] === "papers" && !["scan", "import", "reconnect", "upload"].includes(parts[1]))
    || (parts.length === 2 && parts[0] === "projects")
    || isBlueprintPdfPath(parts)
    || isBlueprintReaderPath(parts)
    || isBlueprintFullTextPath(parts)
    || isBlueprintFullTextStatusPath(parts)
    || isBlueprintTagCandidatesPath(parts)
    || isBlueprintNoteBlocksPath(parts);
}

export function isAllowedBlueprintRequest(method, parts) {
  const normalizedMethod = String(method || "").toUpperCase();
  if (!hasSafeSegments(parts)) return false;
  if (normalizedMethod === "GET") return isAllowedBlueprintPath(parts);
  if (normalizedMethod === "POST") {
    return (parts.length === 1 && parts[0] === "projects")
      || isBlueprintProjectArchivePath(parts)
      || isBlueprintProjectPaperLinksPath(parts)
      || isBlueprintProjectNoteBlockLinksPath(parts)
      || isBlueprintNoteBlocksPath(parts)
      || isBlueprintMetadataEnrichmentPreviewPath(parts)
      || isBlueprintManagedPdfScanPath(parts)
      || isBlueprintManagedPdfImportPath(parts)
      || isBlueprintManagedPdfUploadPath(parts)
      || isBlueprintManagedPdfReconnectPath(parts)
      || isBlueprintPaperRemovePdfPath(parts)
      || isBlueprintPaperArchivePath(parts)
      || isBlueprintPaperTagsPath(parts)
      || (parts.length === 1 && parts[0] === "tags")
      || isBlueprintCanonicalTagAliasesPath(parts)
      || isBlueprintCanonicalTagDeprecatePath(parts)
      || isBlueprintTagCandidateGeneratePath(parts)
      || isBlueprintTagCandidateActionPath(parts)
      || isBlueprintFullTextExtractPath(parts);
  }
  if (normalizedMethod === "PATCH") {
    return isBlueprintMetadataPath(parts)
      || isBlueprintReadingStatusPath(parts)
      || isBlueprintProjectPath(parts)
      || isBlueprintNoteBlockPath(parts)
      || isBlueprintCanonicalTagPath(parts);
  }
  if (normalizedMethod === "PUT") return isBlueprintReadingNotePath(parts);
  if (normalizedMethod === "DELETE") {
    return isBlueprintProjectPaperLinkPath(parts)
      || isBlueprintProjectNoteBlockLinkPath(parts)
      || isBlueprintPaperTagsPath(parts)
      || isBlueprintCanonicalTagAliasesPath(parts);
  }
  return false;
}

export function buildBlueprintTarget(requestUrl, parts, apiUrl) {
  const incoming = new URL(requestUrl);
  const baseUrl = apiUrl.replace(/\/$/, "");
  return `${baseUrl}/${parts.map(encodeURIComponent).join("/")}${incoming.search}`;
}

async function readBoundedCommandBody(request, maxBytes = MAX_COMMAND_BODY_BYTES, binary = false) {
  const declaredLength = Number(request.headers.get("Content-Length"));
  if (Number.isFinite(declaredLength) && declaredLength > maxBytes) return null;
  if (!request.body || typeof request.body.getReader !== "function") {
    const buffer = new Uint8Array(await request.arrayBuffer());
    if (buffer.byteLength > maxBytes) return null;
    return binary ? buffer : new TextDecoder().decode(buffer);
  }
  const reader = request.body.getReader();
  const chunks = [];
  let byteLength = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    byteLength += value.byteLength;
    if (byteLength > maxBytes) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const body = new Uint8Array(byteLength);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return binary ? body : new TextDecoder().decode(body);
}

export async function proxyBlueprintRequest(request, parts, { apiUrl, fetchImpl = fetch, timeoutMs = UPSTREAM_TIMEOUT_MS }) {
  if (!isAllowedBlueprintRequest(request.method, parts)) {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }

  const target = buildBlueprintTarget(request.url, parts, apiUrl);
  const pdfRequest = request.method === "GET" && isBlueprintPdfPath(parts);
  const commandRequest = ["POST", "PATCH", "PUT", "DELETE"].includes(request.method);
  const requestHeaders = new Headers({ Accept: pdfRequest ? "application/pdf" : "application/json" });
  const range = request.headers.get("Range");
  if (pdfRequest && range) requestHeaders.set("Range", range);
  let body;
  if (commandRequest) {
    const contentType = request.headers.get("Content-Type") || "";
    const multipartUpload = request.method === "POST" && isBlueprintManagedPdfUploadPath(parts);
    if (multipartUpload && !/^multipart\/form-data\s*;\s*boundary=/i.test(contentType)) {
      return Response.json({ detail: "Content-Type must be multipart/form-data." }, { status: 415 });
    }
    if (!multipartUpload && !/^application\/json(?:\s*;|$)/i.test(contentType)) {
      return Response.json({ detail: "Content-Type must be application/json." }, { status: 415 });
    }
    requestHeaders.set("Content-Type", contentType);
    try {
      body = await readBoundedCommandBody(
        request,
        multipartUpload ? MAX_PDF_UPLOAD_BODY_BYTES : MAX_COMMAND_BODY_BYTES,
        multipartUpload,
      );
      if (body === null) {
        return Response.json({ detail: "Request body is too large." }, { status: 413 });
      }
    } catch {
      return Response.json({ detail: GENERIC_UNAVAILABLE_DETAIL }, { status: 503 });
    }
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const upstream = await fetchImpl(target, {
      method: request.method,
      headers: requestHeaders,
      body,
      cache: "no-store",
      signal: controller.signal,
    });
    if (upstream.status >= 500) {
      return Response.json(
        { detail: GENERIC_UNAVAILABLE_DETAIL },
        {
          status: 503,
          headers: {
            "X-Blueprint-Error-State": commandRequest
              ? "command-unavailable"
              : "read-model-unavailable",
          },
        },
      );
    }
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
    return Response.json(
      { detail: GENERIC_UNAVAILABLE_DETAIL },
      { status: 503, headers: { "X-Blueprint-Error-State": "api-unavailable" } },
    );
  } finally {
    clearTimeout(timeout);
  }
}

export async function proxyBlueprintGet(request, parts, options) {
  return proxyBlueprintRequest(request, parts, options);
}
