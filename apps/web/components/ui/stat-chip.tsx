import { MISSING } from "@/lib/format";

type StatChipProps = {
  label: string;
  /** Pre-formatted value (use lib/format); null/undefined renders as missing. */
  value: string | null | undefined;
};

export function StatChip({ label, value }: StatChipProps) {
  return (
    <span className="stat-chip">
      <span className="stat-chip__label">{label}</span>
      <span className="stat-chip__value">{value ?? MISSING}</span>
    </span>
  );
}
