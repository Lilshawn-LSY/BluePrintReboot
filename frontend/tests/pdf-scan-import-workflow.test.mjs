import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  isAllowedBlueprintPath,
  isAllowedBlueprintRequest,
  proxyBlueprintRequest,
} from "../app/api/blueprint/[...path]/bridge.mjs";

const API_URL = "http://127.0.0.1:8000";

test("managed PDF scan and import bridge requests are exact POST JSON commands", async () => {
  assert.equal(isAllowedBlueprintRequest("POST", ["papers", "scan"]), true);
  assert.equal(isAllowedBlueprintRequest("POST", ["papers", "import"]), true);
  assert.equal(isAllowedBlueprintPath(["papers", "scan"]), false);
  assert.equal(isAllowedBlueprintPath(["papers", "import"]), false);
  assert.equal(isAllowedBlueprintRequest("GET", ["papers", "scan"]), false);
  assert.equal(isAllowedBlueprintRequest("PATCH", ["papers", "import"]), false);

  for (const [parts, payload] of [
    [["papers", "scan"], {}],
    [["papers", "import"], { relative_paths: ["nested/New.pdf"] }],
  ]) {
    const body = JSON.stringify(payload);
    let receivedUrl = "";
    const response = await proxyBlueprintRequest(
      new Request(`http://localhost/api/blueprint/${parts.join("/")}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Range: "bytes=0-10" },
        body,
      }),
      parts,
      {
        apiUrl: API_URL,
        fetchImpl: async (url, options) => {
          receivedUrl = url;
          assert.equal(options.method, "POST");
          assert.equal(options.headers.get("Content-Type"), "application/json");
          assert.equal(options.headers.get("Range"), null);
          assert.equal(options.body, body);
          return Response.json({ status: "ok" });
        },
      },
    );
    assert.equal(response.status, 200);
    assert.equal(receivedUrl, `${API_URL}/${parts.join("/")}`);
  }
});

test("Library scan/import workflow renders explicit preview, selection, duplicate, and partial-failure states", async () => {
  const [library, inspector, client, types] = await Promise.all([
    readFile(new URL("../app/views/LibraryView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/LibraryPaperInspector.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/api/client.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/api/types.ts", import.meta.url), "utf8"),
  ]);

  assert.match(client, /scanManagedPdfs/);
  assert.match(client, /importManagedPdfs/);
  assert.match(client, /reconnectManagedPdf/);
  assert.match(client, /"\/papers\/scan"/);
  assert.match(client, /"\/papers\/import"/);
  assert.match(client, /"\/papers\/reconnect"/);
  assert.match(types, /ManagedPdfScanCandidate/);
  assert.match(types, /ManagedPdfImportResult/);
  assert.match(library, /Scan \/ import/);
  assert.match(library, /apiClient\.scanManagedPdfs\(\)/);
  assert.match(library, /type="checkbox"/);
  assert.match(library, /toggleSelection/);
  assert.match(library, /Import selected/);
  assert.match(library, /apiClient\.importManagedPdfs\(selectedPaths\)/);
  assert.match(library, /already_registered/);
  assert.match(library, /duplicate_content/);
  assert.match(library, /reconnect_available/);
  assert.match(library, /Reconnect existing Paper/);
  assert.match(library, /PDF command unavailable/);
  assert.match(library, /importResult\.results/);
  assert.match(inspector, /Open Reader/);
  assert.match(library, /Metadata enrichment/);
  assert.match(library, /previewMetadataEnrichment/);
  assert.match(library, /Apply selected fields/);
  assert.doesNotMatch(library, /fetch\s*\(/);
});
