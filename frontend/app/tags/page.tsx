import type { Metadata } from "next";
import { DeferredWorkspaceView } from "../views/DeferredWorkspaceView";

export const metadata: Metadata = { title: "Tags" };
export default function TagsPage() {
  return <DeferredWorkspaceView eyebrow="Knowledge organization" title="Tags" description="Govern canonical tags, aliases, and tag quality across the workspace." apiDescription="Canonical tag listing and governance actions require a future Tag Book API. Tag Manager remains available in Streamlit."><p className="purpose-copy">This route is reserved for canonical vocabulary review, alias visibility, and quality diagnostics. It does not fabricate tag counts or suggestions.</p></DeferredWorkspaceView>;
}
