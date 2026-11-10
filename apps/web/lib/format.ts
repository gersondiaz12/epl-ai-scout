/**
 * Number formatting for stats. One place so every table, chip and bar agrees:
 * fixed decimals per kind of stat, en-GB grouping, a true minus sign, and an
 * en dash for missing data (never 0, which is a real value).
 */

export const MISSING = "–"; // –

const MINUS = "−"; // −

const formatters = new Map<number, Intl.NumberFormat>();

function formatter(decimals: number): Intl.NumberFormat {
  let f = formatters.get(decimals);
  if (!f) {
    f = new Intl.NumberFormat("en-GB", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    formatters.set(decimals, f);
  }
  return f;
}

function isMissing(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined || Number.isNaN(value);
}

/** Generic number with fixed decimals, e.g. 1234.5 -> "1,234.5", -0.3 -> "−0.3". */
export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (isMissing(value)) return MISSING;
  return formatter(decimals).format(value).replace("-", MINUS);
}

/** Per-90 rates always use 2 decimals so columns line up: 0.4 -> "0.40". */
export function formatPer90(value: number | null | undefined): string {
  return formatNumber(value, 2);
}

/** Ratio in 0–1 shown as a percentage with 1 decimal: 0.642 -> "64.2%". */
export function formatPercent(ratio: number | null | undefined, decimals = 1): string {
  if (isMissing(ratio)) return MISSING;
  return `${formatNumber(ratio * 100, decimals)}%`;
}

/** Minutes played, grouped: 2345 -> "2,345". */
export function formatMinutes(value: number | null | undefined): string {
  return formatNumber(value, 0);
}

/** Signed difference for comparisons: 0.12 -> "+0.12", -0.12 -> "−0.12". */
export function formatDelta(value: number | null | undefined, decimals = 2): string {
  if (isMissing(value)) return MISSING;
  const text = formatNumber(value, decimals);
  return value > 0 ? `+${text}` : text;
}
