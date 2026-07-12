import type { ReactNode } from "react";

export function DetailPanel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="detail-panel"><h2>{title}</h2><div className="detail-panel__body">{children}</div></section>;
}
