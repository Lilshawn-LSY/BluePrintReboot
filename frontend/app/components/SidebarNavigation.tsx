"use client";

import { FolderKanban, Gauge, LibraryBig, PanelLeftClose, PanelLeftOpen, Pin, PinOff, Settings, Tags, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const primaryNavigation = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/library", label: "Library", icon: LibraryBig },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/tags", label: "Tags", icon: Tags },
];

const secondaryNavigation = [
  { href: "/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/" || pathname === "/dashboard";
  return pathname === href || pathname.startsWith(`${href}/`);
}

type SidebarNavigationProps = {
  readerMode: boolean;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  readerPinned: boolean;
  onToggleReaderPinned: () => void;
  onReaderClose: () => void;
  onReaderEnter: () => void;
  onReaderLeave: () => void;
};

export function SidebarNavigation({
  readerMode,
  collapsed,
  onToggleCollapsed,
  readerPinned,
  onToggleReaderPinned,
  onReaderClose,
  onReaderEnter,
  onReaderLeave,
}: SidebarNavigationProps) {
  const pathname = usePathname();
  return (
    <aside
      className={readerMode ? "sidebar sidebar--reader" : "sidebar"}
      data-collapsed={collapsed}
      aria-label="Primary navigation"
      onMouseEnter={readerMode ? onReaderEnter : undefined}
      onMouseLeave={readerMode ? onReaderLeave : undefined}
    >
      <div className="sidebar__header">
        <Link href="/dashboard" className="brand" aria-label="BluePrintReboot dashboard">
          <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
            <path className="brand__datum" d="M7 4v24" />
            <path className="brand__construction" d="M10 5h8c4 0 6 2 6 5.5S22 16 18 16h-8zm0 11h9c4 0 6 2.1 6 5.5S23 27 19 27H10z" />
            <path className="brand__body" d="M11 7h7c2.3 0 3.5 1.1 3.5 3.3S20.3 13.5 18 13.5h-7zm0 9h8c2.5 0 3.8 1.7 3.8 4S21.5 24 19 24h-8z" />
          </svg>
          <span className="brand__copy"><strong>BluePrint</strong><small>Research workspace</small></span>
        </Link>
        {readerMode ? (
          <div className="sidebar__reader-actions">
            <button className="sidebar-toggle" type="button" onClick={onToggleReaderPinned} aria-pressed={readerPinned} aria-label={readerPinned ? "Unpin navigation" : "Pin navigation"} title={readerPinned ? "Unpin navigation" : "Pin navigation"}>
              {readerPinned ? <PinOff aria-hidden="true" size={16} /> : <Pin aria-hidden="true" size={16} />}
              <span className="sidebar-toggle__label">{readerPinned ? "Unpin" : "Pin"}</span>
            </button>
            <button className="sidebar-toggle sidebar-toggle--icon" type="button" onClick={onReaderClose} aria-label="Close navigation" title="Close navigation">
              <X aria-hidden="true" size={16} />
            </button>
          </div>
        ) : (
          <button className="sidebar-toggle sidebar-toggle--icon" type="button" onClick={onToggleCollapsed} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {collapsed ? <PanelLeftOpen aria-hidden="true" size={16} /> : <PanelLeftClose aria-hidden="true" size={16} />}
          </button>
        )}
      </div>
      <nav id="primary-navigation" className="sidebar-nav">
        {primaryNavigation.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link key={href} href={href} className="sidebar-link" data-active={active} aria-current={active ? "page" : undefined} aria-label={collapsed ? label : undefined} title={collapsed ? label : undefined}>
              <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <nav className="sidebar-nav sidebar-nav--secondary" aria-label="Workspace settings">
        {secondaryNavigation.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link key={href} href={href} className="sidebar-link" data-active={active} aria-current={active ? "page" : undefined} aria-label={collapsed ? label : undefined} title={collapsed ? label : undefined}>
              <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
