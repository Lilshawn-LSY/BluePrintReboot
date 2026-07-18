import type { Metadata } from "next";
import { ReaderView } from "../../../views/ReaderView";

export const metadata: Metadata = { title: "Reader" };
export default async function ReaderPage({ params }: { params: Promise<{ paperId: string }> }) {
  const { paperId } = await params;
  return <ReaderView paperId={paperId} />;
}
