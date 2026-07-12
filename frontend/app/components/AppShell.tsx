"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { SidebarNavigation } from "./SidebarNavigation";

const routeTitles: Record<string, string> = {
  "/": "Dashboard",
  "/dashboard": "Dashboard",
  "/library": "Library",
  "/papers": "Papers",
  "/projects": "Projects",
  "/tags": "Tags",
  "/settings": "Settings",
};

function currentTitle(pathname: string): string {
  if (pathname.startsWith("/papers/")) return "Paper Detail";
  return routeTitles[pathname] ?? "Workspace";
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      <SidebarNavigation />
      <div className="workspace-frame">
        <header className="top-bar">
          <div className="top-bar__context">
            <span className="top-bar__eyebrow">Workspace</span>
            <span className="top-bar__separator" aria-hidden="true">/</span>
            <strong>{currentTitle(pathname)}</strong>
          </div>
          <span className="version-label">v1.2.0 · read-only shell</span>
        </header>
        <main id="main-content" className="main-content">{children}</main>
      </div>
    </div>
  );
}
