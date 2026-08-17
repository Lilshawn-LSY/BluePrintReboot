const dateFormatter = new Intl.DateTimeFormat("en", {
  dateStyle: "medium",
  timeZone: "UTC",
});

export function formatUiDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateFormatter.format(date);
}

export function formatAuthorSummary(authors: string[], fallback = ""): string {
  const names = authors.filter(Boolean);
  if (names.length === 0) return fallback || "Authors unknown";
  if (names.length === 1) return names[0];
  return `${names[0]} et al.`;
}
