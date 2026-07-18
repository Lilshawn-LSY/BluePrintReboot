import type { ReactNode } from "react";
import { UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";

export function DeferredWorkspaceView({ eyebrow, title, description, apiDescription, children }: { eyebrow: string; title: string; description: string; apiDescription: string; children: ReactNode }) {
  return (
    <div className="page-stack">
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <Section title="Planned workspace" description="This route is part of the stable application shell; its domain API is not available yet.">{children}</Section>
      <UnavailableState title={`${title} API not available in v1.2.2`} description={apiDescription} />
    </div>
  );
}
