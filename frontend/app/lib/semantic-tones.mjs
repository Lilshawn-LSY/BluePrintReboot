/**
 * Semantic colors describe domain meaning. They deliberately do not describe
 * taxonomy, navigation, or general UI decoration.
 */
export const SEMANTIC_TONES = Object.freeze([
  "blue",
  "green",
  "amber",
  "rose",
  "violet",
  "slate",
]);

const STATUS_MARKER_TONES = Object.freeze({
  unread: "slate",
  reading: "blue",
  read: "green",
  finished: "green",
  active: "blue",
  paused: "amber",
  done: "green",
  archived: "slate",
  low: "slate",
  normal: "slate",
  high: "amber",
  urgent: "rose",
  critical: "rose",
  healthy: "green",
  clean: "green",
  available: "green",
  ready: "green",
  success: "green",
  warning: "amber",
  stale: "amber",
  ocr_needed: "amber",
  conflict: "rose",
  failed: "rose",
  failure: "rose",
  offline: "rose",
  unavailable: "rose",
});

const RELATIONSHIP_TONES = Object.freeze({
  related: "slate",
  background: "slate",
  key_reference: "violet",
  supports_project: "green",
  raises_question: "violet",
  idea_for_project: "amber",
});

function normalizedValue(value) {
  return typeof value === "string" ? value.trim().toLowerCase().replaceAll(" ", "_") : "";
}

export function statusMarkerTone(value) {
  return STATUS_MARKER_TONES[normalizedValue(value)];
}

export function inferredStatusMarkerTone(value, presentation) {
  return presentation === "chip" ? undefined : statusMarkerTone(value);
}

export function systemStateTone(value) {
  return statusMarkerTone(value) ?? "slate";
}

export function relationshipTone(value) {
  return RELATIONSHIP_TONES[normalizedValue(value)] ?? "slate";
}
