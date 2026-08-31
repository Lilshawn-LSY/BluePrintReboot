import { StatusBadge } from "./StatusBadge";
import { saveStateLabel } from "../lib/drafts/revision-draft.mjs";
import type { SaveState } from "../lib/drafts/revision-draft.mjs";

export function SaveStatus({ state }: { state: SaveState }) {
  const tone = state === "saved"
    ? "green"
    : state === "unsaved" || state === "saving"
      ? "blue"
      : "rose";
  return <StatusBadge tone={tone}>{saveStateLabel(state)}</StatusBadge>;
}
