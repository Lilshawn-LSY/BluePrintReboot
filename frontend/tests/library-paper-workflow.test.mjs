import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("Library makes the paper collection primary and selects papers into a contextual inspector", async () => {
  const [library, inspector, css] = await Promise.all([
    readFile(new URL("../app/views/LibraryView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/LibraryPaperInspector.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(library, /<PageHeader title="Library"/);
  assert.match(library, /<Section title="Papers">/);
  assert.ok(library.indexOf('<Section title="Papers">') < library.indexOf('title="Scan and import PDFs"'));
  assert.match(library, /placeholder="Search papers…"/);
  assert.match(library, /apiClient\.getPapers\(\{ limit: PAGE_SIZE, offset, archiveStatus, q, tag, year, status: readingStatus \}\)/);
  assert.match(library, /library-paper-row__select/);
  assert.match(library, /aria-pressed=\{selectedPaperId === paper\.paper_id\}/);
  assert.match(library, /onClick=\{\(\) => selectPaper\(paper\.paper_id\)\}/);
  assert.match(library, /<LibraryPaperInspector/);
  assert.doesNotMatch(library, /<th>Actions<\/th>/);
  assert.doesNotMatch(library, />Detail<\/Link>/);
  assert.doesNotMatch(library, />Reader<\/Link>/);

  assert.match(inspector, /apiClient\.getPaper\(paperId\)/);
  assert.match(inspector, /aria-label="Selected paper"/);
  assert.match(inspector, /Open Reader/);
  assert.match(inspector, /View Paper Detail/);
  assert.match(inspector, /Enrich metadata/);
  assert.match(inspector, /No tags yet/);
  assert.match(inspector, /Linked to \$\{count\} project/);
  assert.match(css, /\.library-collection-layout--with-inspector/);
  assert.match(css, /\.library-paper-row\[data-selected="true"\]/);
  assert.match(css, /\.library-paper-inspector__abstract/);
});

test("metadata enrichment remains explicit and contextual to the selected paper", async () => {
  const library = await readFile(new URL("../app/views/LibraryView.tsx", import.meta.url), "utf8");

  assert.match(library, /previewMetadataEnrichment\(paperId\)/);
  assert.match(library, /saveReaderMetadata\(enrichment\.paper_id, changes, enrichment\.metadata_revision\)/);
  assert.match(library, /Review each candidate before applying it\./);
  assert.match(library, /Apply selected fields/);
  assert.match(library, /checked=\{selectedFields\.includes\(field\.field\)\}/);
  assert.match(library, /Candidate details/);
});

test("Paper Detail presents a readable overview and keeps identifiers and organization contextual", async () => {
  const detail = await readFile(new URL("../app/views/PaperDetailView.tsx", import.meta.url), "utf8");

  assert.match(detail, /<Breadcrumbs items=/);
  assert.match(detail, /<PageHeader title=\{resource\.data\.title \|\| "Untitled paper"\}/);
  assert.match(detail, /Open Reader/);
  assert.match(detail, /<Section title="Abstract">/);
  assert.match(detail, /<Section title="Citation">/);
  assert.ok(detail.indexOf('<Section title="Abstract">') < detail.indexOf('<Section title="Citation">'));
  assert.match(detail, /resource\.data\.authors\.join\("; "\)/);
  assert.match(detail, /resource\.data\.doi/);
  assert.match(detail, /resource\.data\.arxiv_id/);
  assert.match(detail, /<DetailPanel title="Organization">/);
  assert.match(detail, /No tags yet/);
  assert.match(detail, /<DetailPanel title="Reading context">/);
  assert.doesNotMatch(detail, /project_id/);
  assert.doesNotMatch(detail, /extracted_text_available|profile_available|metadata_revision/);
});
