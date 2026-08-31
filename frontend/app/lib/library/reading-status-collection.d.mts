export interface ReadingStatusCollectionItem {
  paper_id: string;
  status: string;
}

export interface ReadingStatusCollection<T extends ReadingStatusCollectionItem> {
  items: T[];
}

export function patchReadingStatusCollection<
  Item extends ReadingStatusCollectionItem,
  Collection extends ReadingStatusCollection<Item>,
>(
  collection: Collection,
  paperId: string,
  readingStatus: string,
): Collection;

export function readingStatusChangeRequiresCollectionRefresh(
  activeReadingStatus: string,
  previousStatus: string,
  nextStatus: string,
): boolean;

export function patchPaperReadingStatus<T extends ReadingStatusCollectionItem>(
  paper: T,
  readingStatus: string,
  readingStatusRevision: string,
): T & { reading_status_revision: string };
