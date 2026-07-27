import type { Metadata } from "next";
import { TagsView } from "../views/TagsView";

export const metadata: Metadata = { title: "Tags" };
export default function TagsPage() {
  return <TagsView />;
}
