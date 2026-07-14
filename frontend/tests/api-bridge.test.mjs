import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildBlueprintTarget, isAllowedBlueprintPath, proxyBlueprintGet } from "../app/api/blueprint/[...path]/bridge.mjs";

const API_URL = "http://127.0.0.1:8000";

test("allows only the four read-only API path shapes", () => {
  for (const parts of [["health"], ["library", "status"], ["papers"], ["papers", "paper-123"]]) {
    assert.equal(isAllowedBlueprintPath(parts), true, parts.join("/"));
  }
  for (const parts of [[], ["library"], ["projects"], ["papers", "paper-123", "notes"], ["health", "extra"]]) {
    assert.equal(isAllowedBlueprintPath(parts), false, parts.join("/"));
  }
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
  assert.match(route, /export async function GET\b/);
  assert.doesNotMatch(route, /export (?:async )?function (?:POST|PUT|PATCH|DELETE)\b/);
});
