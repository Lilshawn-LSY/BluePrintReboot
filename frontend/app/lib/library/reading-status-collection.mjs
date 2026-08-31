/**
 * Keep a loaded Library page truthful after the revision-checked status command
 * succeeds. This is intentionally not optimistic: callers invoke it only with
 * the server-confirmed status returned by the command.
 */
export function patchReadingStatusCollection(collection, paperId, readingStatus) {
  let changed = false;
  const items = collection.items.map((paper) => {
    if (paper.paper_id !== paperId || paper.status === readingStatus) return paper;
    changed = true;
    return { ...paper, status: readingStatus };
  });
  return changed ? { ...collection, items } : collection;
}

export function patchPaperReadingStatus(paper, readingStatus, readingStatusRevision) {
  return {
    ...paper,
    status: readingStatus,
    reading_status_revision: readingStatusRevision,
  };
}

/**
 * An exact reading-status filter can exclude the selected row after a change.
 * Other Library filters remain unaffected, so their loaded collection is safe
 * to patch in place.
 */
export function readingStatusChangeRequiresCollectionRefresh(activeReadingStatus, previousStatus, nextStatus) {
  return Boolean(activeReadingStatus) && previousStatus !== nextStatus;
}
