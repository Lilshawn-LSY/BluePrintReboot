export function readerResearchTabFromSearchParams(searchParams) {
  return searchParams.get("noteBlock")?.trim() ? "blocks" : "note";
}

export function readerUtilityFromSearchParams(searchParams) {
  const utility = searchParams.get("utility");
  return utility === "tags" || utility === "full-text" ? utility : null;
}
