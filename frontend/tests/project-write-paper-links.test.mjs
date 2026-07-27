import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sources = Promise.all([
  readFile(new URL("../app/views/ProjectsView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/views/ProjectDetailView.tsx", import.meta.url), "utf8"),
  readFile(new URL("../app/lib/api/client.ts", import.meta.url), "utf8"),
  readFile(new URL("../app/lib/projects/editor-state.mjs", import.meta.url), "utf8"),
]);

test("Project creation is explicit, bounded, and navigates to the created identity", async () => {
  const [projects, , client] = await sources;
  assert.match(projects, /Create Project/);
  assert.match(projects, /maxLength=\{200\}/);
  assert.match(projects, /maxLength=\{5000\}/);
  assert.match(projects, /apiClient\.createProject/);
  assert.match(projects, /response\.project\.project_id/);
  assert.match(client, /method: "POST"/);
  assert.doesNotMatch(projects, /setInterval|setTimeout|onBlur=.*createProject/);
});

test("Project metadata commands require explicit edit, save, cancel, archive, and reload actions", async () => {
  const [, detail, client, editor] = await sources;
  for (const label of ["Edit Project", "Save Project", "Cancel", "Archive Project", "Reload current Project"]) {
    assert.match(detail, new RegExp(label));
  }
  assert.match(detail, /window\.confirm\("Archive this Project\?/);
  assert.match(detail, /does not delete the Project, its Paper links, or any Paper/);
  assert.match(detail, /apiClient\.updateProject/);
  assert.match(detail, /project\.project_revision/);
  assert.match(client, /expected_revision: expectedRevision/);
  assert.match(editor, /preserveProjectDraftAfterFailure/);
  assert.match(editor, /draft is preserved/);
  assert.match(detail, /document\.addEventListener\("click"/);
  assert.doesNotMatch(detail, /onBlur=.*saveProject|setInterval/i);
});

test("Paper linking uses the real bounded Paper index and exact link revision", async () => {
  const [, detail, client] = await sources;
  assert.match(detail, /apiClient\.getPapers\(\{ limit: 100, archiveStatus: "all" \}\)/);
  assert.match(detail, /Retry Paper picker/);
  assert.match(detail, /first 100 existing Papers/);
  assert.match(detail, /apiClient\.addProjectPaperLink/);
  assert.match(detail, /project\.links_revision/);
  assert.match(detail, /exact Paper link already exists; nothing was written/);
  assert.match(client, /expected_links_revision: expectedLinksRevision/);
  assert.doesNotMatch(detail, /sample Paper|const papers\s*=\s*\[/);
});

test("unlink is confirmed and cannot delete a Paper or mutate Note Block links", async () => {
  const [, detail, client] = await sources;
  assert.match(detail, /Remove the Project link/);
  assert.match(detail, /This does not delete the Paper/);
  assert.match(detail, /link\.target_type === "paper"/);
  assert.match(detail, /apiClient\.removeProjectPaperLink/);
  assert.doesNotMatch(client, /deleteProject\s*:|deletePaper\s*:|note-block-links/);
  assert.doesNotMatch(detail, /Add Note Block|Remove Note Block|Create Note Block/);
});

test("archived Projects retain read detail while write controls are absent", async () => {
  const [, detail] = await sources;
  assert.match(detail, /const archived = project\.status === "archived"/);
  assert.match(detail, /\{!archived \?/);
  assert.match(detail, /stored links remain readable/);
  assert.match(detail, /Save or cancel the metadata draft before changing Paper links/);
});
