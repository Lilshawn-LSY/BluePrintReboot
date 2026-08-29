import type { ReactNode } from "react";

type Tone = "neutral" | "healthy" | "warning" | "danger" | "accent";
type Presentation = "label" | "chip" | "badge";
type Taxonomy = "canonical" | "alias" | "candidate";

export function StatusBadge({ tone = "neutral", presentation, taxonomy, children }: { tone?: Tone; presentation?: Presentation; taxonomy?: Taxonomy; children: ReactNode }) {
  const resolvedPresentation = presentation ?? (tone === "warning" || tone === "danger" ? "badge" : "label");
  return <span className={`status-badge status-badge--${resolvedPresentation}`} data-taxonomy={resolvedPresentation === "chip" ? taxonomy ?? "canonical" : undefined} data-tone={tone}>{children}</span>;
}
