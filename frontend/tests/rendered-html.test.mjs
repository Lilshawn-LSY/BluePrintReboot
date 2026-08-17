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

const workerUrl = new URL("../dist/server/index.js", import.meta.url);
workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
const workerPromise = import(workerUrl.href);

async function render(pathname = "/") {
  const { default: worker } = await workerPromise;
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
  for (const label of ["Dashboard", "Library", "Projects", "Tags", "Settings"]) {
    assert.match(html, new RegExp(`>${label}<`));
  }
  assert.match(html, /Loading workspace overview/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Your site is taking shape/i);
});

test("all required routes render inside the shared shell", async () => {
  for (const path of ["/dashboard", "/library", "/papers", "/papers/example-paper", "/papers/example-paper/reader", "/projects", "/projects/example-project", "/tags", "/settings"]) {
    const response = await render(path);
    assert.equal(response.status, 200, path);
    const html = await response.text();
    assert.match(html, /class="app-shell(?:\s|")/, path);
    assert.match(html, /aria-label="Primary navigation"/, path);
  }
});

test("uses a bounded PDF.js Reader with independent metadata and Reading Note commands", async () => {
  const [detail, readerView, reader, adapter, controller, client, shell, sidebar, packageJson, packageLock, workerSource, workerDeclaration] = await Promise.all([
    readFile(new URL("../app/views/PaperDetailView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/ReaderView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/PdfJsReader.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/pdf/pdfjs-adapter.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/pdf/reader-controller.mjs", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/api/client.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/components/AppShell.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/SidebarNavigation.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../package-lock.json", import.meta.url), "utf8"),
    readFile(new URL("../node_modules/pdfjs-dist/legacy/build/pdf.worker.mjs", import.meta.url), "utf8"),
    readFile(new URL("../types/pdf-worker.d.ts", import.meta.url), "utf8"),
  ]);

  assert.match(detail, /Open Reader/);
  assert.match(detail, /encodeURIComponent\(resource\.data\.paper_id\)/);
  assert.match(detail, /Reader unavailable/);
  assert.match(readerView, /title=\{editor\.metadata\.draft\.title \|\| snapshot\.paper\.title\}/);
  assert.match(readerView, /Paper metadata/);
  assert.match(readerView, /Metadata enrichment/);
  assert.match(readerView, /Fetch candidates/);
  assert.match(readerView, /Apply selected fields/);
  assert.match(readerView, /previewMetadataEnrichment/);
  assert.match(readerView, /Complete Reading Note/);
  assert.match(readerView, /Save Metadata/);
  assert.match(readerView, /Save Reading Note/);
  assert.match(readerView, /Reload current metadata/);
  assert.match(readerView, /Reload current Reading Note/);
  assert.match(readerView, /<Breadcrumbs items=/);
  assert.match(readerView, /Loading Reader snapshot/);
  assert.match(readerView, /Managed PDF missing/);
  assert.match(readerView, /<PdfJsReader paperId=\{snapshot\.paper\.paper_id\}/);
  assert.match(readerView, /current\.saved_note_content/);
  assert.match(readerView, /saved_note_unavailable/);
  assert.match(readerView, /reader-note__textarea/);
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
  assert.match(reader, /lifecycleGenerationRef/);
  assert.match(reader, /observeLifecyclePromise\(controller\.destroy\(\), "cleanup"\)/);
  assert.match(readerView, /apiClient\.saveReaderMetadata/);
  assert.match(readerView, /applyMetadataEnrichmentCommandResult/);
  assert.match(readerView, /apiClient\.saveReadingNote/);
  assert.doesNotMatch(readerView, /contentEditable|dangerouslySetInnerHTML|autosave|annotation|highlight/i);
  assert.match(client, /getReaderSnapshot/);
  assert.match(client, /\/papers\/\$\{encodeURIComponent\(paperId\)\}\/reader/);
  assert.match(client, /\/papers\/\$\{encodeURIComponent\(paperId\)\}\/pdf/);
  assert.doesNotMatch(client, /bytes=0-0|getPaperPdf|probePaperPdf/);
  assert.doesNotMatch(client, /http:\/\/127\.0\.0\.1:8000/);
  assert.match(adapter, /typeof window === "undefined"/);
  assert.match(adapter, /import\("pdfjs-dist\/legacy\/build\/pdf\.mjs"\)/);
  assert.match(adapter, /import\("pdfjs-dist\/legacy\/build\/pdf\.worker\.min\.mjs\?url"\)/);
  assert.doesNotMatch(adapter, /import\("pdfjs-dist"\)/);
  assert.doesNotMatch(adapter, /["']pdfjs-dist\/build\/pdf\.worker\.min\.mjs\?url["']/);
  assert.match(workerDeclaration, /declare module "pdfjs-dist\/legacy\/build\/pdf\.worker\.min\.mjs\?url"/);
  assert.doesNotMatch(workerDeclaration, /declare module "pdfjs-dist\/build\/pdf\.worker\.min\.mjs\?url"/);
  assert.doesNotMatch(adapter, /https?:\/\//);
  assert.match(controller, /documentLoadCount/);
  assert.match(controller, /renderCancellationCount/);
  assert.equal(JSON.parse(packageJson).dependencies["pdfjs-dist"], "5.7.284");
  assert.equal(JSON.parse(packageLock).packages[""].dependencies["pdfjs-dist"], "5.7.284");
  assert.match(workerSource, /function onFailure\(ex\) \{\s+if \(terminated\) \{\s+return;/);
  assert.doesNotMatch(workerSource, /function onFailure\(ex\) \{\s+ensureNotTerminated\(\);/);
  assert.match(shell, /isReaderRoute/);
  assert.equal(JSON.parse(packageJson).version, "1.5.12");
  assert.match(shell, /NORMAL_SIDEBAR_PREFERENCE_KEY/);
  assert.match(shell, /packageMetadata\.version/);
  assert.match(shell, /applicationVersion=\{packageMetadata\.version\}/);
  assert.match(sidebar, /v\{applicationVersion\}/);
  assert.doesNotMatch(shell, /Local workspace|version-label/);
  assert.doesNotMatch(shell, /v1\.5\.4|Project commands/);
});

test("production build contains the repository-local PDF.js worker asset", async () => {
  const files = await listFiles(fileURLToPath(new URL("../dist", import.meta.url)));
  assert.ok(files.some((path) => /pdf\.worker\.min-[^/]+\.mjs$/i.test(path)), files.join("\n"));
});

test("Reader snapshot states remain independent and stale paper state is hidden", async () => {
  const [readerView, resourceHook] = await Promise.all([
    readFile(new URL("../app/views/ReaderView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/hooks/useApiResource.ts", import.meta.url), "utf8"),
  ]);

  assert.match(readerView, /reader-snapshot:\$\{paperId\}:\$\{retryCount\}/);
  assert.match(readerView, /apiClient\.getReaderSnapshot\(paperId\)/);
  assert.doesNotMatch(readerView, /apiClient\.getPaper\(paperId\)/);
  assert.match(resourceHook, /if \(state\.resourceKey !== activeResourceKey\) return \{ status: "loading", retry \}/);
  assert.match(readerView, /snapshot\.pdf_state === "missing"/);
  assert.match(readerView, /saved_note_baseline\.exists/);
  assert.match(readerView, /No persisted note exists/);
  assert.match(readerView, /persisted note could not be read/);
  assert.match(readerView, /Retry local API/);
  assert.match(readerView, /<ReaderPdf snapshot=\{snapshot\}/);
  assert.match(readerView, /<ReaderWorkspace key=\{resource\.data\.paper\.paper_id\}/);
  assert.match(readerView, /Discard unsaved Reader changes/);
});

test("keeps tokens, API access, and page views separated", async () => {
  const [css, client, shell, papers, projects, tags, packageJson] = await Promise.all([
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/api/client.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/components/AppShell.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/PapersView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/ProjectsView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/TagsView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  for (const token of ["--color-canvas", "--space-4", "--space-12", "--font-size-base", "--radius-md", "--border", "--shadow-subtle", "--sidebar-width", "--sidebar-collapsed-width", "--control-height", "--content-padding", "--z-sidebar"]) {
    assert.match(css, new RegExp(token));
  }
  assert.match(client, /const API_BASE_URL/);
  assert.match(client, /getHealth/);
  assert.match(client, /getLibraryStatus/);
  assert.match(client, /getPapers/);
  assert.match(client, /getPaper/);
  assert.match(client, /getProjects/);
  assert.match(client, /getProject/);
  assert.match(client, /getTags/);
  assert.match(client, /getTagSummary/);
  assert.doesNotMatch(shell, /fetch\s*\(/);
  assert.doesNotMatch(papers, /fetch\s*\(/);
  assert.doesNotMatch(projects, /fetch\s*\(/);
  assert.doesNotMatch(tags, /fetch\s*\(/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton|drizzle/);
});
