import type { ReactNode } from "react";

type Tone = "neutral" | "slate" | "healthy" | "warning" | "danger" | "accent";
type Presentation = "label" | "chip" | "badge";
type Taxonomy = "canonical" | "alias" | "candidate";

const STATUS_MARKER_TONES: Readonly<Record<string, Tone>> = {
  unread: "neutral",
  reading: "accent",
  read: "healthy",
  finished: "healthy",
  active: "accent",
  paused: "warning",
  done: "healthy",
  archived: "slate",
  low: "slate",
  normal: "slate",
  high: "warning",
  urgent: "danger",
  critical: "danger",
};

export function statusMarkerTone(value: unknown): Tone | undefined {
  if (typeof value !== "string") return undefined;
  return STATUS_MARKER_TONES[value.trim().toLowerCase()];
}

export function StatusBadge({ tone, presentation, taxonomy, children }: { tone?: Tone; presentation?: Presentation; taxonomy?: Taxonomy; children: ReactNode }) {
  // Tags use the canonical-tag treatment; their text must never accidentally become a status tone.
  const inferredTone = presentation === "chip" ? undefined : statusMarkerTone(children);
  const resolvedTone = tone ?? inferredTone ?? "neutral";
  const resolvedPresentation = presentation ?? (tone === "warning" || tone === "danger" ? "badge" : "label");
  return <span className={`status-badge status-badge--${resolvedPresentation}`} data-taxonomy={resolvedPresentation === "chip" ? taxonomy ?? "canonical" : undefined} data-tone={resolvedTone}>{children}</span>;
}
