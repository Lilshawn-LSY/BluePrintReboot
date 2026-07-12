import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request(`http://localhost${pathname}`, { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the stable research workspace shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>BluePrintReboot<\/title>/i);
  assert.match(html, /class="app-shell"/);
  assert.match(html, /aria-label="Primary navigation"/);
  for (const label of ["Dashboard", "Library", "Papers", "Projects", "Tags", "Settings"]) {
    assert.match(html, new RegExp(`>${label}<`));
  }
  assert.match(html, /Loading workspace overview/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Your site is taking shape/i);
});

test("all required routes render inside the shared shell", async () => {
  for (const path of ["/dashboard", "/library", "/papers", "/papers/example-paper", "/projects", "/tags", "/settings"]) {
    const response = await render(path);
    assert.equal(response.status, 200, path);
    const html = await response.text();
    assert.match(html, /class="app-shell"/, path);
    assert.match(html, /aria-label="Primary navigation"/, path);
  }
});

test("keeps tokens, API access, and page views separated", async () => {
  const [css, client, shell, papers, project, packageJson] = await Promise.all([
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/api/client.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/components/AppShell.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/PapersView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/projects/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  for (const token of ["--color-canvas", "--space-4", "--font-size-base", "--radius-md", "--border", "--shadow-subtle", "--sidebar-width", "--header-height", "--content-padding", "--z-sidebar"]) {
    assert.match(css, new RegExp(token));
  }
  assert.match(client, /const API_BASE_URL/);
  assert.match(client, /getHealth/);
  assert.match(client, /getLibraryStatus/);
  assert.match(client, /getPapers/);
  assert.match(client, /getPaper/);
  assert.doesNotMatch(shell, /fetch\s*\(/);
  assert.doesNotMatch(papers, /fetch\s*\(/);
  assert.match(project, /API not available|future read\/write project API/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton|drizzle/);
});
