import type { ReactNode } from "react";

type Tone = "neutral" | "healthy" | "warning" | "danger" | "accent";

export function StatusBadge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className="status-badge" data-tone={tone}>{children}</span>;
}
