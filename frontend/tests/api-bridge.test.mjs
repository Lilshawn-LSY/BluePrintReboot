import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildBlueprintTarget,
  isAllowedBlueprintPath,
  isAllowedBlueprintRequest,
  isBlueprintMetadataPath,
  isBlueprintPdfPath,
  isBlueprintReaderPath,
  isBlueprintReadingNotePath,
  proxyBlueprintGet,
  proxyBlueprintRequest,
} from "../app/api/blueprint/[...path]/bridge.mjs";

const API_URL = "http://127.0.0.1:8000";

test("allows the bounded read routes plus the exact managed PDF and Reader routes", () => {
  for (const parts of [["health"], ["library", "status"], ["papers"], ["papers", "paper-123"], ["projects"], ["projects", "project-123"], ["tags"], ["tags", "summary"], ["papers", "paper-123", "pdf"], ["papers", "paper-123", "reader"]]) {
    assert.equal(isAllowedBlueprintPath(parts), true, parts.join("/"));
  }
  for (const parts of [[], ["library"], ["settings"], ["tags", "unknown"], ["projects", "project-123", "edit"], ["papers", "paper-123", "notes"], ["papers", "paper-123", "pdf", "raw"], ["papers", "paper-123", "reader", "raw"], ["health", "extra"]]) {
    assert.equal(isAllowedBlueprintPath(parts), false, parts.join("/"));
  }
  assert.equal(isBlueprintPdfPath(["papers", "paper-123", "pdf"]), true);
  assert.equal(isBlueprintPdfPath(["papers", "paper-123"]), false);
  assert.equal(isBlueprintReaderPath(["papers", "paper-123", "reader"]), true);
  assert.equal(isBlueprintReaderPath(["papers", "paper-123", "reader", "raw"]), false);
  assert.equal(isBlueprintMetadataPath(["papers", "paper-123", "metadata"]), true);
  assert.equal(isBlueprintReadingNotePath(["papers", "paper-123", "reading-note"]), true);
});

test("allows only the exact method and path pairs for Reader commands", () => {
  assert.equal(isAllowedBlueprintRequest("PATCH", ["papers", "paper-1", "metadata"]), true);
  assert.equal(isAllowedBlueprintRequest("PUT", ["papers", "paper-1", "reading-note"]), true);
  for (const [method, parts] of [
    ["PUT", ["papers", "paper-1", "metadata"]],
    ["PATCH", ["papers", "paper-1", "reading-note"]],
    ["POST", ["papers", "paper-1", "metadata"]],
    ["DELETE", ["papers", "paper-1", "reading-note"]],
    ["PATCH", ["papers", "paper-1", "reader"]],
    ["GET", ["papers", "paper-1", "metadata"]],
  ]) {
    assert.equal(isAllowedBlueprintRequest(method, parts), false, `${method} ${parts.join("/")}`);
  }
});

test("rejects decoded and encoded path tricks before contacting upstream", async () => {
  for (const parts of [
    ["papers", "..", "metadata"],
    ["papers", ".", "reading-note"],
    ["papers", "paper/other", "metadata"],
    ["papers", "paper\\other", "metadata"],
    ["papers", "paper%2Fother", "metadata"],
    ["papers", "%252e%252e", "reading-note"],
  ]) {
    let fetched = false;
    const response = await proxyBlueprintRequest(
      new Request("http://localhost/api/blueprint/rejected", {
        method: parts[2] === "metadata" ? "PATCH" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      }),
      parts,
      { apiUrl: API_URL, fetchImpl: async () => { fetched = true; return new Response(); } },
    );
    assert.equal(response.status, 404, parts.join("/"));
    assert.equal(fetched, false, parts.join("/"));
  }
});

test("forwards command JSON bodies and Content-Type without forwarding Range", async () => {
  const payload = JSON.stringify({ changes: { title: "Exact draft" }, expected_revision: "a".repeat(64) });
  let requestedUrl;
  const response = await proxyBlueprintRequest(
    new Request("http://localhost/api/blueprint/papers/paper%201/metadata", {
      method: "PATCH",
      headers: { "Content-Type": "application/json; charset=utf-8", Range: "bytes=0-10" },
      body: payload,
    }),
    ["papers", "paper 1", "metadata"],
    {
      apiUrl: API_URL,
      fetchImpl: async (url, options) => {
        requestedUrl = url;
        assert.equal(options.method, "PATCH");
        assert.equal(options.headers.get("Accept"), "application/json");
        assert.equal(options.headers.get("Content-Type"), "application/json; charset=utf-8");
        assert.equal(options.headers.get("Range"), null);
        assert.equal(options.body, payload);
        return Response.json({ status: "saved" });
      },
    },
  );
  assert.equal(response.status, 200);
  assert.equal(requestedUrl, `${API_URL}/papers/paper%201/metadata`);
});

test("rejects command bodies without JSON Content-Type", async () => {
  let fetched = false;
  const response = await proxyBlueprintRequest(
    new Request("http://localhost/api/blueprint/papers/paper-1/reading-note", {
      method: "PUT",
      headers: { "Content-Type": "text/plain" },
      body: "private draft",
    }),
    ["papers", "paper-1", "reading-note"],
    { apiUrl: API_URL, fetchImpl: async () => { fetched = true; return new Response(); } },
  );
  assert.equal(response.status, 415);
  assert.equal(fetched, false);
});

test("maps command body read failures to a controlled local 503", async () => {
  let fetched = false;
  const response = await proxyBlueprintRequest(
    {
      method: "PUT",
      url: "http://localhost/api/blueprint/papers/paper-1/reading-note",
      headers: new Headers({ "Content-Type": "application/json" }),
      text: async () => { throw new Error("private body read failure"); },
    },
    ["papers", "paper-1", "reading-note"],
    { apiUrl: API_URL, fetchImpl: async () => { fetched = true; return new Response(); } },
  );
  assert.equal(response.status, 503);
  assert.equal(fetched, false);
  assert.deepEqual(await response.json(), { detail: "Local BluePrintReboot API is unavailable." });
});

test("forwards the exact Reader route as JSON without a Range header", async () => {
  let requestedUrl;
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/papers/paper%201/reader?mode=readonly", { headers: { Range: "bytes=0-10" } }),
    ["papers", "paper 1", "reader"],
    {
      apiUrl: API_URL,
      fetchImpl: async (url, options) => {
        requestedUrl = url;
        assert.equal(options.headers.get("Accept"), "application/json");
        assert.equal(options.headers.get("Range"), null);
        return Response.json({ paper: { paper_id: "paper 1" } });
      },
    },
  );

  assert.equal(response.status, 200);
  assert.equal(requestedUrl, `${API_URL}/papers/paper%201/reader?mode=readonly`);
});

test("returns 404 for an unlisted path without contacting the upstream API", async () => {
  let fetched = false;
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/settings"),
    ["settings"],
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

test("forwards the bounded Projects and Tags GET contracts", async () => {
  const requests = [];
  for (const [url, parts] of [
    ["http://localhost/api/blueprint/projects?limit=100&offset=0", ["projects"]],
    ["http://localhost/api/blueprint/projects/project%201?links_limit=100", ["projects", "project 1"]],
    ["http://localhost/api/blueprint/tags?limit=100&offset=0", ["tags"]],
    ["http://localhost/api/blueprint/tags/summary", ["tags", "summary"]],
  ]) {
    const response = await proxyBlueprintGet(
      new Request(url),
      parts,
      {
        apiUrl: API_URL,
        fetchImpl: async (target, options) => {
          requests.push([target, options.method, options.headers.get("Range")]);
          return Response.json({ ok: true });
        },
      },
    );
    assert.equal(response.status, 200);
  }
  assert.deepEqual(requests, [
    [`${API_URL}/projects?limit=100&offset=0`, "GET", null],
    [`${API_URL}/projects/project%201?links_limit=100`, "GET", null],
    [`${API_URL}/tags?limit=100&offset=0`, "GET", null],
    [`${API_URL}/tags/summary`, "GET", null],
  ]);
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

test("preserves unsatisfiable PDF Range responses and safe size metadata", async () => {
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/papers/paper-1/pdf", { headers: { Range: "bytes=999-1000" } }),
    ["papers", "paper-1", "pdf"],
    {
      apiUrl: API_URL,
      fetchImpl: async (_url, options) => {
        assert.equal(options.headers.get("Range"), "bytes=999-1000");
        return new Response(null, { status: 416, headers: { "Content-Range": "bytes */100" } });
      },
    },
  );

  assert.equal(response.status, 416);
  assert.equal(response.headers.get("Content-Range"), "bytes */100");
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
  assert.equal(response.headers.get("X-Blueprint-Error-State"), "read-model-unavailable");
});

test("maps fetch failures to the generic local 503", async () => {
  const response = await proxyBlueprintGet(
    new Request("http://localhost/api/blueprint/library/status"),
    ["library", "status"],
    { apiUrl: API_URL, fetchImpl: async () => { throw new Error("private network detail"); } },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { detail: "Local BluePrintReboot API is unavailable." });
  assert.equal(response.headers.get("X-Blueprint-Error-State"), "api-unavailable");
});

test("the route exposes only GET plus the two bounded write methods", async () => {
  const route = await readFile(new URL("../app/api/blueprint/[...path]/route.ts", import.meta.url), "utf8");
  const bridge = await readFile(new URL("../app/api/blueprint/[...path]/bridge.mjs", import.meta.url), "utf8");
  assert.match(route, /export async function GET\b/);
  assert.match(route, /export async function PATCH\b/);
  assert.match(route, /export async function PUT\b/);
  assert.doesNotMatch(route, /export (?:async )?function (?:POST|DELETE)\b/);
  assert.doesNotMatch(bridge, /await upstream\.(?:text|json|arrayBuffer)\(/);
});
