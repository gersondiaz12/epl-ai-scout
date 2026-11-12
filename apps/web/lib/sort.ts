export type SortDir = "ascending" | "descending";

export type SortState<K extends string> = { key: K; dir: SortDir };

/**
 * Compares two cell values. Missing values (null) always sink to the bottom,
 * whatever the direction, so "–" never outranks a real number.
 * Returns 0 for ties so callers can chain a tie-breaker.
 */
export function compareValues(
  a: number | string | null,
  b: number | string | null,
  dir: SortDir,
): number {
  if (a === null || b === null) {
    if (a === b) return 0;
    return a === null ? 1 : -1;
  }
  if (a === b) return 0;
  const order =
    typeof a === "string" && typeof b === "string" ? a.localeCompare(b) : Number(a) - Number(b);
  return dir === "ascending" ? order : -order;
}

/** Clicking the active column flips it; a new column starts in its natural direction. */
export function nextSort<K extends string>(
  current: SortState<K>,
  key: K,
  firstDir: SortDir,
): SortState<K> {
  if (current.key === key) {
    return { key, dir: current.dir === "ascending" ? "descending" : "ascending" };
  }
  return { key, dir: firstDir };
}
