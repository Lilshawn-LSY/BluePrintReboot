import { proxyBlueprintGet } from "./bridge.mjs";

const LOCAL_API_URL = (process.env.BLUEPRINT_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export async function GET(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxyBlueprintGet(request, path, { apiUrl: LOCAL_API_URL });
}
