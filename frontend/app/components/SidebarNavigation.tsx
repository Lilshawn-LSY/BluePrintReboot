"use client";

import { BookOpen, FolderKanban, Gauge, LibraryBig, Settings, Tags } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/library", label: "Library", icon: LibraryBig },
  { href: "/papers", label: "Papers", icon: BookOpen },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/tags", label: "Tags", icon: Tags },
  { href: "/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/" || pathname === "/dashboard";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SidebarNavigation() {
  const pathname = usePathname();
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <Link href="/dashboard" className="brand" aria-label="BluePrintReboot dashboard">
        <span className="brand__mark" aria-hidden="true">B</span>
        <span><strong>BluePrint</strong><small>Research workspace</small></span>
      </Link>
      <nav className="sidebar-nav">
        {navigation.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link key={href} href={href} className="sidebar-link" data-active={active} aria-current={active ? "page" : undefined}>
              <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="sidebar__footer"><span className="connection-dot" aria-hidden="true" />Local workspace</div>
    </aside>
  );
}
