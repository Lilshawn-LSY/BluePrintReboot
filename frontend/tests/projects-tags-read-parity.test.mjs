import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sources = Promise.all([
  readFile(new URL("../app/projects/page.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/projects/[projectId]/page.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/tags/page.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/views/ProjectsView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/views/ProjectDetailView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/views/TagsView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/components/AsyncStates.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/hooks/useApiResource.ts", import.meta.url), "utf8"),
  readFile(new URL("../app/lib/api/client.ts", import.meta.url), "utf8"),
]);

test("Projects and Tags routes no longer render deferred placeholders", async () => {
  const [projectsPage, projectDetailPage, tagsPage, projects, projectDetail, tags] = await sources;

  assert.match(projectsPage, /<ProjectsView \/>/);
  assert.match(projectDetailPage, /<ProjectDetailView projectId=\{projectId\} \/>/);
  assert.match(tagsPage, /<TagsView \/>/);
  for (const source of [projectsPage, projectDetailPage, tagsPage, projects, projectDetail, tags]) {
    assert.doesNotMatch(source, /DeferredWorkspaceView/);
  }
});

test("Projects renders real collection fields and bounded linked-paper detail", async () => {
  const [, , , projects, projectDetail, , , , client] = await sources;

  assert.match(projects, /apiClient\.getProjects\(\{ limit: 100 \}\)/);
  for (const field of ["project.name", "project.project_id", "project.status", "project.priority", "project.tags", "project.linked_paper_count", "project.updated_at"]) {
    assert.match(projects, new RegExp(field.replace(".", "\\.")));
  }
  assert.match(projectDetail, /apiClient\.getProject\(projectId, \{ linksLimit: 100 \}\)/);
  assert.match(projectDetail, /link\.link_type/);
  assert.match(projectDetail, /link\.target_state/);
  assert.match(projectDetail, /link\.paper\.title/);
  assert.match(projectDetail, /link\.paper_id/);
  assert.match(projectDetail, /Linked paper unavailable/);
  assert.match(client, /links_limit/);
  assert.match(client, /links_offset/);
  assert.doesNotMatch(projects + projectDetail, /<button\b|Create Project|Edit Project|Archive Project|Delete Project|Unlink paper/);
});

test("Tags renders canonical identity, label, category, aliases, status, and real summary counts", async () => {
  const [, , , , , tags, , , client] = await sources;

  assert.match(tags, /apiClient\.getTags\(\{ limit: 100 \}\)/);
  assert.match(tags, /apiClient\.getTagSummary\(\)/);
  for (const field of ["tag.label", "tag.canonical_key", "tag.category", "tag.aliases", "tag.status", "tag.suggestion_strength"]) {
    assert.match(tags, new RegExp(field.replace(".", "\\.")));
  }
  assert.match(tags, /summary\.candidate_count/);
  assert.match(tags, /summary\.quality_counts\.high/);
  assert.match(tags, /Candidate summary unavailable/);
  assert.match(tags, /No candidate evidence/);
  assert.match(client, /\/tags\/summary/);
  assert.doesNotMatch(tags, /<button\b|Create Tag|Apply Tag|Remove Tag|Edit Alias|Merge Tags/);
});

test("shared async states cover loading, empty, offline, read-model failure, not-found, and retry", async () => {
  const [, , , projects, projectDetail, tags, asyncStates, resourceHook] = await sources;

  for (const source of [projects, projectDetail, tags]) {
    assert.match(source, /status === "loading"/);
    assert.match(source, /status === "unavailable"/);
    assert.match(source, /status === "error"/);
    assert.match(source, /onRetry=\{resource\.retry\}/);
    assert.match(source, /<EmptyState/);
  }
  assert.match(projectDetail, /status === "not-found"/);
  assert.match(asyncStates, />Retry<\/button>/);
  assert.match(resourceHook, /setAttempt\(\(current\) => current \+ 1\)/);
  assert.match(resourceHook, /resourceKey !== activeResourceKey/);
});

test("read parity contains no fabricated records and preserves existing views", async () => {
  const [, , , projects, projectDetail, tags] = await sources;
  const [library, papers, reader] = await Promise.all([
    readFile(new URL("../app/views/LibraryView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/PapersView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/views/ReaderView.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(projects, /never substitutes sample Projects/);
  assert.match(tags, /never supplies generated examples/);
  assert.doesNotMatch(projects + projectDetail + tags, /const\s+(?:projects|tags|papers)\s*=\s*\[/i);
  assert.match(library, /apiClient\.getLibraryStatus/);
  assert.match(papers, /apiClient\.getPapers/);
  assert.match(reader, /apiClient\.getReaderSnapshot/);
});
