import { StatusBadge } from "./StatusBadge";
import { saveStateLabel } from "../lib/drafts/revision-draft.mjs";
import type { SaveState } from "../lib/drafts/revision-draft.mjs";

export function SaveStatus({ state }: { state: SaveState }) {
  const tone = state === "saved"
    ? "accent"
    : state === "unsaved" || state === "saving"
      ? "neutral"
      : "danger";
  return <StatusBadge tone={tone}>{saveStateLabel(state)}</StatusBadge>;
}
