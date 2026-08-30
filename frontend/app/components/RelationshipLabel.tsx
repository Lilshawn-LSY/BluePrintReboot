import type { ProjectLinkType } from "../lib/api/types";

const RELATIONSHIP_LABELS: Record<ProjectLinkType, string> = {
  related: "Related",
  background: "Background",
  key_reference: "Key reference",
  supports_project: "Supports Project",
  raises_question: "Raises question",
  idea_for_project: "Idea for Project",
};

export function relationshipLabel(type: ProjectLinkType | string): string {
  return RELATIONSHIP_LABELS[type as ProjectLinkType] ?? type.replaceAll("_", " ");
}

export function RelationshipLabel({ type }: { type: ProjectLinkType | string }) {
  return <span className="relationship-label" data-relationship={type}>{relationshipLabel(type)}</span>;
}
