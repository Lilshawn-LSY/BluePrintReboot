import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("the shared shell preserves normal navigation preference independently from Reader overlay navigation", async () => {
  const [shell, sidebar, breadcrumbs, css] = await Promise.all([
    readFile(new URL("../app/components/AppShell.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/SidebarNavigation.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/Breadcrumbs.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(shell, /NORMAL_SIDEBAR_PREFERENCE_KEY/);
  assert.match(shell, /sessionStorage\.getItem/);
  assert.match(shell, /sessionStorage\.setItem/);
  assert.match(shell, /useSyncExternalStore/);
  assert.match(shell, /NORMAL_SIDEBAR_PREFERENCE_EVENT/);
  assert.match(shell, /isReaderRoute/);
  assert.match(shell, /readerSidebarPinned/);
  assert.match(shell, /readerSidebarOpen/);
  assert.match(shell, /reader-navigation-zone/);
  assert.doesNotMatch(shell, /packageMetadata|Local workspace|version-label/);

  assert.match(sidebar, /Collapse sidebar/);
  assert.match(sidebar, /Expand sidebar/);
  assert.match(sidebar, /Pin navigation/);
  assert.match(sidebar, /Close navigation/);
  assert.match(sidebar, /aria-label=\{collapsed \? label : undefined\}/);

  assert.match(breadcrumbs, /aria-label="Breadcrumb"/);
  assert.match(breadcrumbs, /aria-current="page"/);
  for (const selector of [
    ".app-shell--reader",
    "--sidebar-collapsed-width",
    ".reader-navigation-zone",
    "data-reader-sidebar-open",
    ".breadcrumbs__current",
    "--space-12",
    "--control-height",
  ]) {
    assert.match(css, new RegExp(selector.replaceAll(".", "\\.")));
  }
});
