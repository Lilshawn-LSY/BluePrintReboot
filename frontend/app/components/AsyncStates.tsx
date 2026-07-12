import { AlertCircle, CloudOff, FileQuestion, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

function StateFrame({ icon, title, description, role }: { icon: ReactNode; title: string; description: string; role?: "status" | "alert" }) {
  return (
    <div className="state-frame" role={role}>
      <span className="state-frame__icon" aria-hidden="true">{icon}</span>
      <div><h2>{title}</h2><p>{description}</p></div>
    </div>
  );
}

export function LoadingState({ label = "Loading workspace data" }: { label?: string }) {
  return <StateFrame role="status" icon={<LoaderCircle className="loading-icon" size={20} />} title={label} description="Reading from the local BluePrintReboot API." />;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <StateFrame role="status" icon={<FileQuestion size={20} />} title={title} description={description} />;
}

export function ErrorState({ description }: { description: string }) {
  return <StateFrame role="alert" icon={<AlertCircle size={20} />} title="Unable to load this view" description={description} />;
}

export function UnavailableState({ title = "Local API unavailable", description = "Start the local FastAPI service to connect this view. The application shell remains available offline." }: { title?: string; description?: string }) {
  return <StateFrame role="status" icon={<CloudOff size={20} />} title={title} description={description} />;
}
