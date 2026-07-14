const GENERIC_UNAVAILABLE_DETAIL = "Local BluePrintReboot API is unavailable.";

export function isAllowedBlueprintPath(parts) {
  if (!Array.isArray(parts) || !parts.every((part) => typeof part === "string" && part.length > 0)) return false;
  const path = parts.join("/");
  return path === "health" || path === "library/status" || path === "papers" || (parts.length === 2 && parts[0] === "papers");
}

export function buildBlueprintTarget(requestUrl, parts, apiUrl) {
  const incoming = new URL(requestUrl);
  const baseUrl = apiUrl.replace(/\/$/, "");
  return `${baseUrl}/${parts.map(encodeURIComponent).join("/")}${incoming.search}`;
}

export async function proxyBlueprintGet(request, parts, { apiUrl, fetchImpl = fetch }) {
  if (!isAllowedBlueprintPath(parts)) return Response.json({ detail: "Not found." }, { status: 404 });

  const target = buildBlueprintTarget(request.url, parts, apiUrl);
  try {
    const upstream = await fetchImpl(target, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (upstream.status >= 500) return Response.json({ detail: GENERIC_UNAVAILABLE_DETAIL }, { status: 503 });
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return Response.json({ detail: GENERIC_UNAVAILABLE_DETAIL }, { status: 503 });
  }
}
