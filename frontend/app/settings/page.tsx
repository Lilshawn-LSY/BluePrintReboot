import type { Metadata } from "next";
import { DeferredWorkspaceView } from "../views/DeferredWorkspaceView";

export const metadata: Metadata = { title: "Settings" };
export default function SettingsPage() {
  return <DeferredWorkspaceView eyebrow="Application configuration" title="Settings" description="Review paths, backup, diagnostics, and developer configuration." apiDescription="Configuration and diagnostic settings do not yet have a frontend-safe API. Use Streamlit Settings for current controls."><p className="purpose-copy">Future settings will expose explicit safe configuration contracts. Absolute paths, environment variables, secrets, and write actions are intentionally absent here.</p></DeferredWorkspaceView>;
}
