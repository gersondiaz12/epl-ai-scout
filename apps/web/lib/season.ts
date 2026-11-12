/** API season labels use a hyphen ("2026-27"); display them with an en dash. */
export function formatSeason(label: string): string {
  return label.replace("-", "–");
}
