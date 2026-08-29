import type { ReactNode } from "react";

type Tone = "neutral" | "healthy" | "warning" | "danger" | "accent";
type Presentation = "label" | "chip" | "badge";

export function StatusBadge({ tone = "neutral", presentation, children }: { tone?: Tone; presentation?: Presentation; children: ReactNode }) {
  const resolvedPresentation = presentation ?? (tone === "warning" || tone === "danger" ? "badge" : "label");
  return <span className={`status-badge status-badge--${resolvedPresentation}`} data-tone={tone}>{children}</span>;
}
