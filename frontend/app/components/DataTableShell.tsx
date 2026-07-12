import type { ReactNode } from "react";

export function DataTableShell({ children, label }: { children: ReactNode; label: string }) {
  return <div className="data-table-shell" role="region" aria-label={label} tabIndex={0}>{children}</div>;
}
