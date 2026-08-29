"use client";

import { usePathname } from "next/navigation";
import { PanelLeftOpen } from "lucide-react";
import { useState, useSyncExternalStore, type ReactNode } from "react";
import { SidebarNavigation } from "./SidebarNavigation";

const NORMAL_SIDEBAR_PREFERENCE_KEY = "blueprint.ui.normal-sidebar-collapsed";
const NORMAL_SIDEBAR_PREFERENCE_EVENT = "blueprint.ui.normal-sidebar-changed";

function getNormalSidebarPreference(): boolean {
  if (typeof window === "undefined") return false;
  return window.sessionStorage.getItem(NORMAL_SIDEBAR_PREFERENCE_KEY) === "true";
}

function subscribeToNormalSidebarPreference(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(NORMAL_SIDEBAR_PREFERENCE_EVENT, onStoreChange);
  return () => window.removeEventListener(NORMAL_SIDEBAR_PREFERENCE_EVENT, onStoreChange);
}

function isReaderRoute(pathname: string): boolean {
  return /^\/papers\/[^/]+\/reader\/?$/.test(pathname);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const readerRoute = isReaderRoute(pathname);
  const normalSidebarCollapsed = useSyncExternalStore(
    subscribeToNormalSidebarPreference,
    getNormalSidebarPreference,
    () => false,
  );
  const [readerSidebarOpen, setReaderSidebarOpen] = useState(false);
  const [readerSidebarPinned, setReaderSidebarPinned] = useState(false);

  const toggleNormalSidebar = () => {
    window.sessionStorage.setItem(NORMAL_SIDEBAR_PREFERENCE_KEY, String(!normalSidebarCollapsed));
    window.dispatchEvent(new Event(NORMAL_SIDEBAR_PREFERENCE_EVENT));
  };

  return (
    <div
      className={readerRoute ? "app-shell app-shell--reader" : "app-shell"}
      data-sidebar-collapsed={!readerRoute && normalSidebarCollapsed}
      data-reader-sidebar-open={readerRoute && readerSidebarOpen}
    >
      <a className="skip-link" href="#main-content">Skip to content</a>
      {readerRoute ? (
        <div className="reader-navigation-zone">
          <button
            className="reader-navigation-trigger"
            type="button"
            aria-label={readerSidebarOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={readerSidebarOpen}
            aria-controls="primary-navigation"
            onClick={() => setReaderSidebarOpen((current) => !current)}
          >
            <PanelLeftOpen aria-hidden="true" size={16} />
          </button>
        </div>
      ) : null}
      <SidebarNavigation
        readerMode={readerRoute}
        collapsed={readerRoute ? false : normalSidebarCollapsed}
        onToggleCollapsed={toggleNormalSidebar}
        readerPinned={readerSidebarPinned}
        onToggleReaderPinned={() => {
          setReaderSidebarPinned((current) => !current);
          setReaderSidebarOpen(true);
        }}
        onReaderClose={() => setReaderSidebarOpen(false)}
        onReaderEnter={() => setReaderSidebarOpen(true)}
        onReaderLeave={() => {
          if (!readerSidebarPinned) setReaderSidebarOpen(false);
        }}
      />
      <div className="workspace-frame">
        <main id="main-content" className="main-content">{children}</main>
      </div>
    </div>
  );
}
