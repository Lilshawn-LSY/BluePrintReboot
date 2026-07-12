import type { ReactNode } from "react";

export function Toolbar({ children, label = "Page tools" }: { children: ReactNode; label?: string }) {
  return <div className="toolbar" role="group" aria-label={label}>{children}</div>;
}
