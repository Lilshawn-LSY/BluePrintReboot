import type { Metadata } from "next";
import { ProjectDetailView } from "../../views/ProjectDetailView";

export const metadata: Metadata = { title: "Project Detail" };
export default async function ProjectDetailPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <ProjectDetailView projectId={projectId} />;
}
