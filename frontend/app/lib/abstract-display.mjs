/**
 * Prepares stored abstracts for display without changing the stored value.
 * Single line breaks usually come from metadata extraction; blank lines remain
 * meaningful paragraph boundaries.
 */
export function abstractDisplayParagraphs(value) {
  return String(value ?? "")
    .replace(/\r\n?/g, "\n")
    .trim()
    .split(/\n[\t ]*\n+/)
    .map((paragraph) => paragraph.replace(/[\t ]*\n[\t ]*/g, " ").replace(/[\t ]{2,}/g, " ").trim())
    .filter(Boolean);
}
