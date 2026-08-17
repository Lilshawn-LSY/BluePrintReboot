export async function collectAllPaginatedItems(loadPage, pageSize = 100) {
  if (!Number.isInteger(pageSize) || pageSize < 1) {
    throw new TypeError("pageSize must be a positive integer.");
  }
  const items = [];
  let offset = 0;
  let expectedTotal = null;
  while (true) {
    const page = await loadPage({ limit: pageSize, offset });
    if (!page || !Array.isArray(page.items) || !Number.isInteger(page.total)) {
      throw new TypeError("The paginated response is malformed.");
    }
    if (expectedTotal === null) expectedTotal = page.total;
    if (page.total !== expectedTotal) {
      throw new Error("The paginated collection changed while it was being loaded.");
    }
    items.push(...page.items);
    if (!page.has_more) return items;
    if (page.items.length === 0) {
      throw new Error("The paginated response did not make progress.");
    }
    offset += page.items.length;
  }
}
