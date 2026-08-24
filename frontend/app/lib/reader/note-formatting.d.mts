export type PaperNoteFormatAction =
  | "heading"
  | "bold"
  | "italic"
  | "bullets"
  | "numbered"
  | "task"
  | "quote"
  | "link";

export type PaperNoteFormatResult = {
  value: string;
  selectionStart: number;
  selectionEnd: number;
};

export function formatPaperNoteMarkdown(
  value: string,
  selectionStart: number,
  selectionEnd: number,
  action: PaperNoteFormatAction,
  options?: { url?: string },
): PaperNoteFormatResult;
