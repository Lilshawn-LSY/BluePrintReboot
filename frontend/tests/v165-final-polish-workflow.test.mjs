import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sources = Promise.all([
  readFile(new URL("../app/views/ReaderView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/views/LibraryView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/components/LibraryPaperInspector.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/components/NoteBlocksWorkspace.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/views/ProjectDetailView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/views/TagsView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/components/SidebarNavigation.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  readFile(new URL("../app/lib/api/client.ts", import.meta.url), "utf8"),
  readFile(new URL("../app/api/blueprint/[...path]/bridge.mjs", import.meta.url), "utf8"),
]);

test("Reader reserves structural space for the navigation trigger and keeps Library untruncated", async () => {
  const [reader, , , , , , , css] = await sources;
  assert.match(reader, /reader-workspace__navigation-slot/);
  assert.match(css, /grid-template-columns: var\(--reader-navigation-slot\) minmax\(0, 1fr\) auto/);
  assert.match(css, /\.breadcrumbs li:first-child, \.breadcrumbs li:last-child \{ flex: 0 0 auto;/);
  assert.match(css, /\.breadcrumbs li:nth-child\(2\) \{ flex: 1 1 auto;/);
  assert.match(css, /\.reader-navigation-zone \{[^}]*left: var\(--content-padding\);/);
});

test("relationship labels, tag cleanup, and constructed brand mark retain the restrained grammar", async () => {
  const [, , , blocks, project, tags, sidebar, css] = await sources;
  assert.match(project, /<RelationshipLabel type=\{link\.link_type\}/);
  assert.match(blocks, /<RelationshipLabel type=\{link\.link_type\}/);
  assert.match(css, /\.relationship-label \{/);
  assert.match(css, /data-relationship="supports_project"/);
  assert.doesNotMatch(tags, /<th>Status<\/th>/);
  assert.match(tags, /Advanced lifecycle/);
  assert.match(sidebar, /<svg className="brand__mark"/);
  assert.match(sidebar, /aria-hidden="true" focusable="false"/);
});

test("Library keeps operations bounded while supporting PDF picker and drag/drop validation", async () => {
  const [, library, inspector, , , , , css, client, bridge] = await sources;
  assert.match(library, /operation-result-strip/);
  assert.match(library, /library-operation-drawer/);
  assert.match(library, /library-drop-overlay/);
  assert.match(library, /Drop PDFs to import/);
  assert.match(library, /accept="application\/pdf,.pdf"/);
  assert.match(library, /uploadManagedPdfs/);
  assert.match(library, /Only PDF files can be imported/);
  assert.match(inspector, /Remove PDF file/);
  assert.match(inspector, /Remove Paper from Library/);
  assert.match(inspector, /Permanent deletion is intentionally unavailable/);
  assert.match(css, /\.library-operation-drawer \{[^}]*overflow-y: auto/);
  assert.match(client, /removeManagedPdf/);
  assert.match(client, /archivePaper/);
  assert.match(bridge, /isBlueprintManagedPdfUploadPath/);
});

test("reading status and new Note Blocks use explicit safe mutation paths", async () => {
  const [reader, , inspector, blocks, , , , , client] = await sources;
  assert.match(reader, /saveReadingStatus/);
  assert.match(inspector, /saveReadingStatus/);
  assert.match(client, /saveReadingStatus/);
  assert.match(blocks, /: \[block, \.\.\.collection\.items\]/);
  assert.match(blocks, /setExpandedBlockId\(response\.block\.id\)/);
  assert.match(blocks, /editorTitleRef\.current\?\.focus/);
});
