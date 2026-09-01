import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Dashboard exposes one next research action before secondary context", async () => {
  const dashboard = await source("../app/views/DashboardView.tsx");

  assert.match(dashboard, /title="Resume research"/);
  assert.match(dashboard, /Continue reading/);
  assert.match(dashboard, /Reconnect PDF/);
  assert.match(dashboard, /title="Resume a draft"/);
  assert.match(dashboard, /Open Project/);
  assert.match(dashboard, /title="Action required"/);
  assert.ok(dashboard.indexOf('title="Resume research"') < dashboard.indexOf('title="Recent Projects"'));
  assert.ok(dashboard.indexOf('title="Recent Projects"') < dashboard.indexOf('title="Action required"'));
});

test("selected-Paper inspector has a bounded focus and action contract", async () => {
  const [inspector, library, hook, css] = await Promise.all([
    source("../app/components/LibraryPaperInspector.tsx"),
    source("../app/views/LibraryView.tsx"),
    source("../app/hooks/useContextSurface.ts"),
    source("../app/globals.css"),
  ]);

  assert.match(inspector, /useContextSurface/);
  assert.match(inspector, /initialFocusRef: closeButtonRef/);
  assert.match(inspector, /Close selected paper inspector/);
  assert.match(inspector, /Continue in Reader/);
  assert.match(inspector, /Review PDF recovery/);
  assert.match(inspector, /Paper maintenance/);
  assert.match(library, /selectionControls\.current\.get\(dismissedPaperId\)\?\.focus\(\)/);
  assert.match(hook, /event\.key !== "Escape"/);
  assert.match(hook, /initialFocusRef\?\.current/);
  assert.match(css, /\.library-paper-inspector \{ min-width: 0; max-height: calc\(100dvh - var\(--space-8\)\);[\s\S]*overflow-y: auto; overscroll-behavior: contain;/);
});

test("Reader and Library reuse contextual-surface behavior without duplicating save state", async () => {
  const [reader, inspector] = await Promise.all([
    source("../app/views/ReaderView.tsx"),
    source("../app/components/LibraryPaperInspector.tsx"),
  ]);

  assert.match(reader, /useContextSurface/);
  assert.match(reader, /active: Boolean\(activeUtility\)/);
  assert.match(reader, /Research panel: Note, Blocks, and Details/);
  assert.match(reader, /reader-panel-mode-heading/);
  assert.match(reader, /<h2 id="reading-note-editor-title">Note<\/h2>/);
  assert.equal((reader.match(/<SaveStatus state=\{editor\.note\.saveState\}/g) ?? []).length, 1);
  assert.equal((reader.match(/<SaveStatus state=\{editor\.metadata\.saveState\}/g) ?? []).length, 1);
  assert.match(inspector, /onDismiss/);
});

test("dossiers and taxonomy distinguish primary research context from maintenance", async () => {
  const [paper, project, tags, css] = await Promise.all([
    source("../app/views/PaperDetailView.tsx"),
    source("../app/views/ProjectDetailView.tsx"),
    source("../app/views/TagsView.tsx"),
    source("../app/globals.css"),
  ]);

  assert.match(paper, /paper-dossier-summary/);
  assert.match(paper, /Canonical Tags/);
  assert.match(paper, /Linked research/);
  assert.match(paper, /Imported keywords/);
  assert.match(paper, /Citation and metadata review/);
  assert.ok(paper.indexOf('title="Canonical Tags"') < paper.indexOf('Citation and metadata review'));
  assert.match(project, /Research question \/ working context/);
  assert.match(project, /Linked Papers/);
  assert.match(project, /Linked Note Blocks/);
  assert.match(tags, /Generated candidates/);
  assert.match(tags, /Canonical Tag registry/);
  assert.match(tags, /Imported keywords are never changed here/);
  assert.match(css, /:focus-visible \{ outline: 2px solid var\(--blue-700\);/);
  assert.match(css, /\.text-link, \.back-link \{[\s\S]*text-decoration: underline/);
});
