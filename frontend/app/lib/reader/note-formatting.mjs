const BLOCK_ACTIONS = new Set(["heading", "bullets", "numbered", "task", "quote"]);

function clamp(value, lower, upper) {
  return Math.min(Math.max(value, lower), upper);
}

function normalizedSelection(text, selectionStart, selectionEnd) {
  const length = text.length;
  const start = clamp(Number.isFinite(selectionStart) ? selectionStart : length, 0, length);
  const end = clamp(Number.isFinite(selectionEnd) ? selectionEnd : start, start, length);
  return { start, end };
}

function selectedLineRange(text, start, end) {
  const lineStart = text.lastIndexOf("\n", Math.max(0, start - 1)) + 1;
  const finalCharacter = end > start ? end - 1 : end;
  const lineEndIndex = text.indexOf("\n", finalCharacter);
  return {
    start: lineStart,
    end: lineEndIndex === -1 ? text.length : lineEndIndex,
  };
}

function listContent(line) {
  const indentation = line.match(/^\s*/)?.[0] ?? "";
  const remainder = line.slice(indentation.length).replace(/^(?:(?:[-+*])\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+(?:\[[ xX]\]\s+)?)/, "");
  return { indentation, content: remainder };
}

function headingContent(line) {
  const indentation = line.match(/^\s*/)?.[0] ?? "";
  return { indentation, content: line.slice(indentation.length).replace(/^#{1,6}\s*/, "") };
}

function quoteContent(line) {
  const indentation = line.match(/^\s*/)?.[0] ?? "";
  return { indentation, content: line.slice(indentation.length).replace(/^>\s?/, "") };
}

function lineTransform(line, action, index) {
  if (action === "heading") {
    const { indentation, content } = headingContent(line);
    return { value: `${indentation}## ${content}`, originalPrefixLength: line.length - content.length, nextPrefixLength: indentation.length + 3 };
  }
  if (action === "quote") {
    const { indentation, content } = quoteContent(line);
    return { value: `${indentation}> ${content}`, originalPrefixLength: line.length - content.length, nextPrefixLength: indentation.length + 2 };
  }
  const { indentation, content } = listContent(line);
  const prefix = action === "bullets"
    ? "- "
    : action === "numbered"
      ? `${index + 1}. `
      : "- [ ] ";
  return { value: `${indentation}${prefix}${content}`, originalPrefixLength: line.length - content.length, nextPrefixLength: indentation.length + prefix.length };
}

function replaceBlockLines(text, selection, action) {
  const range = selectedLineRange(text, selection.start, selection.end);
  const original = text.slice(range.start, range.end);
  const lines = original.split("\n");
  const transformed = lines.map((line, index) => lineTransform(line, action, index));
  const nextSegment = transformed.map((line) => line.value).join("\n");
  const value = `${text.slice(0, range.start)}${nextSegment}${text.slice(range.end)}`;

  if (selection.start !== selection.end) {
    return {
      value,
      selectionStart: range.start,
      selectionEnd: range.start + nextSegment.length,
    };
  }

  const current = transformed[0] ?? { value: "", originalPrefixLength: 0, nextPrefixLength: 0 };
  const contentOffset = Math.max(0, selection.start - range.start - current.originalPrefixLength);
  const caret = range.start + Math.min(current.value.length, current.nextPrefixLength + contentOffset);
  return { value, selectionStart: caret, selectionEnd: caret };
}

function wrapInline(text, selection, marker, placeholder) {
  const selected = text.slice(selection.start, selection.end);
  const content = selected || placeholder;
  const value = `${text.slice(0, selection.start)}${marker}${content}${marker}${text.slice(selection.end)}`;
  const selectionStart = selection.start + marker.length;
  return {
    value,
    selectionStart,
    selectionEnd: selectionStart + content.length,
  };
}

function insertLink(text, selection, url) {
  const selected = text.slice(selection.start, selection.end);
  const label = selected || "link text";
  const href = String(url || "https://").trim() || "https://";
  const value = `${text.slice(0, selection.start)}[${label}](${href})${text.slice(selection.end)}`;
  if (!selected) {
    return {
      value,
      selectionStart: selection.start + 1,
      selectionEnd: selection.start + 1 + label.length,
    };
  }
  const urlStart = selection.start + label.length + 3;
  return {
    value,
    selectionStart: urlStart,
    selectionEnd: urlStart + href.length,
  };
}

/**
 * Format one Markdown-compatible Paper Note selection without changing its
 * storage model. The returned selection is ready to apply to the textarea.
 */
export function formatPaperNoteMarkdown(value, selectionStart, selectionEnd, action, options = {}) {
  const text = String(value);
  const selection = normalizedSelection(text, selectionStart, selectionEnd);
  if (BLOCK_ACTIONS.has(action)) return replaceBlockLines(text, selection, action);
  if (action === "bold") return wrapInline(text, selection, "**", "bold text");
  if (action === "italic") return wrapInline(text, selection, "*", "italic text");
  if (action === "link") return insertLink(text, selection, options.url);
  return { value: text, selectionStart: selection.start, selectionEnd: selection.end };
}
