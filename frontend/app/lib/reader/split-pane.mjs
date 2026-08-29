export const DEFAULT_RESEARCH_PANEL_WIDTH = 400;
export const MIN_RESEARCH_PANEL_WIDTH = 320;
export const MAX_RESEARCH_PANEL_WIDTH = 520;

export function clampResearchPanelWidth(value, minimum = MIN_RESEARCH_PANEL_WIDTH, maximum = MAX_RESEARCH_PANEL_WIDTH) {
  const numeric = Number(value);
  const safeValue = Number.isFinite(numeric) ? numeric : DEFAULT_RESEARCH_PANEL_WIDTH;
  return Math.min(maximum, Math.max(minimum, Math.round(safeValue)));
}

export function researchPanelWidthFromPointer({ containerRight, clientX, minimum, maximum }) {
  return clampResearchPanelWidth(
    Number(containerRight) - Number(clientX),
    minimum,
    maximum,
  );
}
