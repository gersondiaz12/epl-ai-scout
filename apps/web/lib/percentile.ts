/** Percentile helpers shared by bars, table cell colouring and radars. */

export type PercentileBin = 1 | 2 | 3 | 4 | 5;

/** Clamp to 0–100 and round to a whole percentile. */
export function normalizePercentile(value: number): number {
  return Math.round(Math.min(100, Math.max(0, value)));
}

/** Map 0–100 onto the five colour bins defined as --pct-1 … --pct-5. */
export function percentileBin(value: number): PercentileBin {
  const p = normalizePercentile(value);
  if (p >= 80) return 5;
  if (p >= 60) return 4;
  if (p >= 40) return 3;
  if (p >= 20) return 2;
  return 1;
}
