"use client";

import Link from "next/link";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";

/** Legacy collection URL retained as a gentle, non-destructive signpost. */
export function PapersView() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Collection" title="Papers" description="Library is the primary Paper collection surface." />
      <Section title="Open Library" description="Search, browse, filter, scan, import, enrich, and repair managed Papers from one coherent workflow.">
        <Link className="reader-action" href="/library">Go to Library</Link>
      </Section>
    </div>
  );
}
