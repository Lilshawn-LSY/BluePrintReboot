import { proxyBlueprintRequest } from "./bridge.mjs";

const LOCAL_API_URL = (process.env.BLUEPRINT_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export async function GET(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxyBlueprintRequest(request, path, { apiUrl: LOCAL_API_URL });
}

export async function POST(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxyBlueprintRequest(request, path, { apiUrl: LOCAL_API_URL });
}

export async function PATCH(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxyBlueprintRequest(request, path, { apiUrl: LOCAL_API_URL });
}

export async function PUT(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxyBlueprintRequest(request, path, { apiUrl: LOCAL_API_URL });
}

export async function DELETE(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxyBlueprintRequest(request, path, { apiUrl: LOCAL_API_URL });
}
