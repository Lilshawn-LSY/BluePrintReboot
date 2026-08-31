export type SemanticTone = "blue" | "green" | "amber" | "rose" | "violet" | "slate";

export const SEMANTIC_TONES: readonly SemanticTone[];

export function statusMarkerTone(value: unknown): SemanticTone | undefined;
export function inferredStatusMarkerTone(value: unknown, presentation?: "label" | "chip" | "badge"): SemanticTone | undefined;
export function systemStateTone(value: unknown): SemanticTone;
export function relationshipTone(value: unknown): SemanticTone;
