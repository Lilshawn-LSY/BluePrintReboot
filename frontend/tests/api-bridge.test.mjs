import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildBlueprintTarget, isAllowedBlueprintPath, isBlueprintPdfPath, proxyBlueprintGet } from "../app/api/blueprint/[...path]/bridge.mjs";

const API_URL = "http://127.0.0.1:8000";

test("allows the existing read routes plus the exact managed PDF route", () => {
  for (const parts of [["health"], ["library", "status"], ["papers"], ["papers", "paper-123"], ["papers", "paper-123", "pdf"]]) {
    assert.equal(isAllowedBlueprintPath(parts), true, parts.join("/"));
  }
  for (const parts of [[], ["library"], ["projects"], ["papers", "paper-123", "notes"], ["papers", "paper-123", "pdf", "raw"], ["health", "extra"]]) {
    assert.equal(isAllowedBlueprintPath(parts), false, parts.join("/"));
  }
  assert.equal(isBlueprintPdfPath(["papers", "paper-123", "pdf"]), true);
  assert.equal(isBlueprintPdfPath(["papers", "paper-123"]), false);
});

test("returns 404 for an unlisted path without contacting the upstream API", async () => {
  let fetched = false;
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/projects"),
    ["projects"],
    { apiUrl: API_URL, fetchImpl: async () => { fetched = true; return new Response(); } },
  );

  assert.equal(response.status, 404);
  assert.equal(fetched, false);
  assert.deepEqual(await response.json(), { detail: "Not found." });
});

test("forwards query parameters and safely encodes paper ids", async () => {
  assert.equal(
    buildBlueprintTarget("http://localhost/api/blueprint/papers?limit=5&archive_status=all", ["papers"], `${API_URL}/`),
    `${API_URL}/papers?limit=5&archive_status=all`,
  );

  let requestedUrl;
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/papers/paper%201?view=detail"),
    ["papers", "paper 1"],
    {
      apiUrl: API_URL,
      fetchImpl: async (url) => {
        requestedUrl = url;
        return Response.json({ paper_id: "paper 1" });
      },
    },
  );

  assert.equal(response.status, 200);
  assert.equal(requestedUrl, `${API_URL}/papers/paper%201?view=detail`);
});

test("preserves an upstream 404 response", async () => {
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/papers/missing"),
    ["papers", "missing"],
    {
      apiUrl: API_URL,
      fetchImpl: async () => Response.json({ detail: "Paper not found." }, { status: 404 }),
    },
  );

  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { detail: "Paper not found." });
});

test("streams PDF bytes and preserves only safe representation headers", async () => {
  const bytes = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x00, 0xff]);
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/papers/paper-1/pdf"),
    ["papers", "paper-1", "pdf"],
    {
      apiUrl: API_URL,
      fetchImpl: async (_url, options) => {
        assert.equal(options.headers.get("Accept"), "application/pdf");
        return new Response(bytes, {
          headers: {
            "Content-Type": "application/pdf",
            "Content-Length": String(bytes.length),
            "Accept-Ranges": "bytes",
            "ETag": '"safe-etag"',
            "Last-Modified": "Sat, 18 Jul 2026 00:00:00 GMT",
            "Content-Disposition": 'inline; filename="paper.pdf"',
            "X-Private-Path": "C:/private/library/paper.pdf",
          },
        });
      },
    },
  );

  assert.deepEqual(new Uint8Array(await response.arrayBuffer()), bytes);
  for (const name of ["Content-Type", "Content-Length", "Accept-Ranges", "ETag", "Last-Modified", "Content-Disposition"]) {
    assert.ok(response.headers.get(name), name);
  }
  assert.equal(response.headers.get("X-Private-Path"), null);
});

test("forwards PDF byte ranges and preserves partial response headers", async () => {
  let forwardedRange;
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/papers/paper-1/pdf", { headers: { Range: "bytes=10-19" } }),
    ["papers", "paper-1", "pdf"],
    {
      apiUrl: API_URL,
      fetchImpl: async (_url, options) => {
        forwardedRange = options.headers.get("Range");
        return new Response(new Uint8Array([1, 2, 3]), {
          status: 206,
          headers: {
            "Content-Type": "application/pdf",
            "Content-Range": "bytes 10-12/100",
            "Accept-Ranges": "bytes",
          },
        });
      },
    },
  );

  assert.equal(forwardedRange, "bytes=10-19");
  assert.equal(response.status, 206);
  assert.equal(response.headers.get("Content-Range"), "bytes 10-12/100");
  assert.deepEqual(new Uint8Array(await response.arrayBuffer()), new Uint8Array([1, 2, 3]));
});

test("preserves a PDF endpoint 404 without exposing an upstream origin", async () => {
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/papers/missing/pdf"),
    ["papers", "missing", "pdf"],
    {
      apiUrl: API_URL,
      fetchImpl: async () => Response.json({ detail: "Managed PDF not found." }, { status: 404 }),
    },
  );

  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { detail: "Managed PDF not found." });
  assert.equal(response.headers.get("Location"), null);
});

test("maps upstream 5xx responses to the generic local 503", async () => {
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/health"),
    ["health"],
    {
      apiUrl: API_URL,
      fetchImpl: async () => Response.json({ detail: "private upstream error" }, { status: 500 }),
    },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { detail: "Local BluePrintReboot API is unavailable." });
});

test("maps fetch failures to the generic local 503", async () => {
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/library/status"),
    ["library", "status"],
    { apiUrl: API_URL, fetchImpl: async () => { throw new Error("private network detail"); } },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { detail: "Local BluePrintReboot API is unavailable." });
});

test("the route exposes GET only and no write method", async () => {
  const route = await readFile(new URL("../app/api/blueprint/[...path]/route.ts", import.meta.url), "utf8");
  const bridge = await readFile(new URL("../app/api/blueprint/[...path]/bridge.mjs", import.meta.url), "utf8");
  assert.match(route, /export async function GET\b/);
  assert.doesNotMatch(route, /export (?:async )?function (?:POST|PUT|PATCH|DELETE)\b/);
  assert.doesNotMatch(bridge, /await upstream\.(?:text|json|arrayBuffer)\(/);
});
