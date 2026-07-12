import type { Metadata } from "next";
import { DeferredWorkspaceView } from "../views/DeferredWorkspaceView";

export const metadata: Metadata = { title: "Projects" };
export default function ProjectsPage() {
  return <DeferredWorkspaceView eyebrow="Research organization" title="Projects" description="Organize papers around research goals, questions, and bodies of work." apiDescription="Project listing, membership, and editing require a future read/write project API. Existing project workflows remain in Streamlit."><p className="purpose-copy">This page will connect research goals to papers and useful note context. No projects are shown until a real project contract is available.</p></DeferredWorkspaceView>;
}
