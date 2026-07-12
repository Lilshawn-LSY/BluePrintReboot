import type { Metadata } from "next";
import { PaperDetailView } from "../../views/PaperDetailView";

export const metadata: Metadata = { title: "Paper Detail" };
export default async function PaperDetailPage({ params }: { params: Promise<{ paperId: string }> }) {
  const { paperId } = await params;
  return <PaperDetailView paperId={paperId} />;
}
