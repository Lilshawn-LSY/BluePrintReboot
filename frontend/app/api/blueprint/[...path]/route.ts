const LOCAL_API_URL = (process.env.BLUEPRINT_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function allowedPath(parts: string[]): boolean {
  const path = parts.join("/");
  return path === "health" || path === "library/status" || path === "papers" || (parts.length === 2 && parts[0] === "papers");
}

export async function GET(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!allowedPath(path)) return Response.json({ detail: "Not found." }, { status: 404 });

  const incoming = new URL(request.url);
  const target = `${LOCAL_API_URL}/${path.map(encodeURIComponent).join("/")}${incoming.search}`;
  try {
    const upstream = await fetch(target, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (upstream.status >= 500) return Response.json({ detail: "Local BluePrintReboot API is unavailable." }, { status: 503 });
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return Response.json({ detail: "Local BluePrintReboot API is unavailable." }, { status: 503 });
  }
}
