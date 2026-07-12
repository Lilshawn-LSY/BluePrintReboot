import type { Metadata } from "next";
import { PapersView } from "../views/PapersView";

export const metadata: Metadata = { title: "Papers" };
export default function PapersPage() { return <PapersView />; }
