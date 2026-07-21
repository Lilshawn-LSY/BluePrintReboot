import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (await Promise.all(entries.map(async (entry) => {
    const path = `${directory}/${entry.name}`;
    return entry.isDirectory() ? listFiles(path) : [path];
  }))).flat();
}

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
  for (const path of ["/dashboard", "/library", "/papers", "/papers/example-paper", "/papers/example-paper/reader", "/projects", "/tags", "/settings"]) {
    const response = await render(path);
    assert.equal(response.status, 200, path);
    const html = await response.text();
    assert.match(html, /class="app-shell"/, path);
    assert.match(html, /aria-label="Primary navigation"/, path);
  }
});

test("uses a bounded PDF.js Reader as the primary read-only same-origin viewer", async () => {
  const [detail, readerView, reader, adapter, controller, client, shell, packageJson, packageLock] = await Promise.all([
    readFile(new URL("../app/views/PaperDetailView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/ReaderView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/PdfJsReader.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/pdf/pdfjs-adapter.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/pdf/reader-controller.mjs", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/api/client.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/components/AppShell.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../package-lock.json", import.meta.url), "utf8"),
  ]);

  assert.match(detail, /Open Reader/);
  assert.match(detail, /encodeURIComponent\(resource\.data\.paper_id\)/);
  assert.match(detail, /Reader unavailable/);
  assert.match(readerView, /title=\{resource\.data\.title\}/);
  assert.match(readerView, /Read-only context/);
  assert.match(readerView, /Back to Paper Detail/);
  assert.match(readerView, /Loading paper metadata/);
  assert.match(readerView, /Managed PDF missing/);
  assert.match(readerView, /<PdfJsReader paperId=\{paper\.paper_id\}/);
  assert.doesNotMatch(readerView, /<object\b/);
  assert.match(reader, /<canvas\b/);
  assert.match(reader, /Previous PDF page/);
  assert.match(reader, /Next PDF page/);
  assert.match(reader, /PDF page number/);
  assert.match(reader, /Zoom out/);
  assert.match(reader, /Zoom in/);
  assert.match(reader, /Reset PDF zoom/);
  assert.match(reader, /Loading PDF\.js Reader/);
  assert.match(reader, /Retry PDF\.js/);
  assert.match(reader, /Use native viewer fallback/);
  assert.match(reader, /if \(state\.mode === "fallback"\)/);
  assert.match(reader, /role="img" aria-label=\{`PDF page/);
  assert.match(reader, /Browser PDF viewer unavailable/);
  assert.match(reader, /<object[^>]+data=\{pdfUrl\}[^>]+type="application\/pdf"/s);
  assert.match(reader, /NEXT_PUBLIC_BLUEPRINT_READER_DIAGNOSTICS === "1"/);
  assert.match(readerView, /write action remain in Streamlit|write actions remain in Streamlit/);
  assert.doesNotMatch(readerView, /note editor|autosave|annotation|highlight/i);
  assert.match(client, /\/papers\/\$\{encodeURIComponent\(paperId\)\}\/pdf/);
  assert.doesNotMatch(client, /bytes=0-0|getPaperPdf|probePaperPdf/);
  assert.doesNotMatch(client, /http:\/\/127\.0\.0\.1:8000/);
  assert.match(adapter, /typeof window === "undefined"/);
  assert.match(adapter, /import\("pdfjs-dist"\)/);
  assert.match(adapter, /pdf\.worker\.min\.mjs\?url/);
  assert.doesNotMatch(adapter, /https?:\/\//);
  assert.match(controller, /documentLoadCount/);
  assert.match(controller, /renderCancellationCount/);
  assert.equal(JSON.parse(packageJson).dependencies["pdfjs-dist"], "6.1.200");
  assert.equal(JSON.parse(packageLock).packages[""].dependencies["pdfjs-dist"], "6.1.200");
  assert.match(shell, /return "Reader"/);
});

test("production build contains the repository-local PDF.js worker asset", async () => {
  const files = await listFiles(fileURLToPath(new URL("../dist", import.meta.url)));
  assert.ok(files.some((path) => /pdf\.worker\.min-[^/]+\.mjs$/i.test(path)), files.join("\n"));
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
