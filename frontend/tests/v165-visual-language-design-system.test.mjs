import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("shared rules, square working surfaces, and quiet metadata labels define the v1.6.5 language", async () => {
  const [css, statusBadge] = await Promise.all([
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../app/components/StatusBadge.tsx", import.meta.url), "utf8"),
  ]);

  for (const token of ["--color-rule-faint", "--rule-faint", "--rule-strong", "--shadow-overlay", "--font-structural"]) {
    assert.match(css, new RegExp(token));
  }
  assert.match(css, /\.data-table-shell \{ overflow-x: auto; background: transparent; border-top: var\(--rule-strong\); border-bottom: var\(--rule-strong\);/);
  assert.match(css, /\.toolbar \{[^}]*background: transparent; border: 0; border-bottom: var\(--rule-strong\); border-radius: 0;/);
  assert.match(css, /\.reader-utility-drawer \{[^}]*box-shadow: var\(--shadow-overlay\);/);
  assert.match(css, /\.reader-page-surface \{[^}]*box-shadow:/);
  assert.match(statusBadge, /type Presentation = "label" \| "chip" \| "badge"/);
  assert.match(statusBadge, /tone === "warning" \|\| tone === "danger" \? "badge" : "label"/);
  assert.match(statusBadge, /status-badge--\$\{resolvedPresentation\}/);
});

test("collections use labels for ordinary state and chips only for taxonomy", async () => {
  const [library, paperDetail, projects, tags, reader] = await Promise.all([
    readFile(new URL("../app/views/LibraryView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/PaperDetailView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/ProjectsView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/TagsView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/ReaderView.tsx", import.meta.url), "utf8"),
  ]);

  for (const source of [library, paperDetail, projects, tags]) {
    assert.match(source, /presentation="chip"/);
  }
  assert.match(library, /<td className="structural-value">\{paper\.year \|\| "—"\}<\/td>/);
  assert.match(paperDetail, /<StatusBadge tone="warning">Archived<\/StatusBadge>/);
  assert.match(projects, /project\.status === "archived" \? "warning" : "neutral"/);
  assert.match(reader, /snapshot\.paper\.lifecycle_state !== "active" \? <StatusBadge tone="warning">/);
});
