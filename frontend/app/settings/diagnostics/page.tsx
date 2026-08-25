import type { Metadata } from "next";
import { DiagnosticsView } from "../../views/SettingsView";

export const metadata: Metadata = { title: "Diagnostics" };

export default function DiagnosticsPage() {
  return <DiagnosticsView />;
}
