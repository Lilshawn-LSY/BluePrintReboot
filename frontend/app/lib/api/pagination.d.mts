export interface Page<T> {
  items: T[];
  total: number;
  has_more: boolean;
}

export function collectAllPaginatedItems<T>(
  loadPage: (options: { limit: number; offset: number }) => Promise<Page<T>>,
  pageSize?: number,
): Promise<T[]>;
