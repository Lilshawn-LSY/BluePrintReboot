import assert from "node:assert/strict";
import test from "node:test";

import { formatPaperNoteMarkdown } from "../app/lib/reader/note-formatting.mjs";

test("Paper Note inline formatting wraps the selection and keeps it active", () => {
  const bold = formatPaperNoteMarkdown("selected text", 0, 8, "bold");
  assert.equal(bold.value, "**selected** text");
  assert.deepEqual([bold.selectionStart, bold.selectionEnd], [2, 10]);

  const italic = formatPaperNoteMarkdown("text", 4, 4, "italic");
  assert.equal(italic.value, "text*italic text*");
  assert.deepEqual([italic.selectionStart, italic.selectionEnd], [5, 16]);
});

test("Paper Note block formatting is line-aware, idempotent, and keeps a useful caret", () => {
  const heading = formatPaperNoteMarkdown("# Heading", 4, 4, "heading");
  assert.equal(heading.value, "## Heading");
  assert.deepEqual([heading.selectionStart, heading.selectionEnd], [5, 5]);

  const bullets = formatPaperNoteMarkdown("line one\nline two", 0, 17, "bullets");
  assert.equal(bullets.value, "- line one\n- line two");
  assert.deepEqual([bullets.selectionStart, bullets.selectionEnd], [0, bullets.value.length]);
  assert.equal(formatPaperNoteMarkdown(bullets.value, 0, bullets.value.length, "bullets").value, bullets.value);

  const numbered = formatPaperNoteMarkdown("first\nsecond", 0, 12, "numbered");
  assert.equal(numbered.value, "1. first\n2. second");

  const task = formatPaperNoteMarkdown("item", 0, 4, "task");
  assert.equal(task.value, "- [ ] item");
  assert.equal(formatPaperNoteMarkdown(task.value, 0, task.value.length, "task").value, task.value);

  const quote = formatPaperNoteMarkdown("quoted", 2, 2, "quote");
  assert.equal(quote.value, "> quoted");
  assert.deepEqual([quote.selectionStart, quote.selectionEnd], [4, 4]);
});

test("Paper Note link formatting selects the URL or a useful editable label", () => {
  const selected = formatPaperNoteMarkdown("citation", 0, 8, "link", { url: "https://example.test/paper" });
  assert.equal(selected.value, "[citation](https://example.test/paper)");
  assert.deepEqual([selected.selectionStart, selected.selectionEnd], [11, 37]);

  const empty = formatPaperNoteMarkdown("", 0, 0, "link", { url: "https://" });
  assert.equal(empty.value, "[link text](https://)");
  assert.deepEqual([empty.selectionStart, empty.selectionEnd], [1, 10]);
});
