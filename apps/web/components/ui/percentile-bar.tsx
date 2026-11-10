import type { CSSProperties } from "react";
import { normalizePercentile, percentileBin } from "@/lib/percentile";

type PercentileBarProps = {
  /** Stat name, e.g. "Progressive passes". */
  label: string;
  /** Percentile rank 0–100 against the comparison pool. */
  percentile: number;
  /** Pre-formatted raw value shown beside the label, e.g. "4.12 per 90". */
  raw?: string;
};

/** Use inside a `.pct-list` so the layout adapts to the container width. */
export function PercentileBar({ label, percentile, raw }: PercentileBarProps) {
  const p = normalizePercentile(percentile);

  return (
    <div className="pct-bar" data-bin={percentileBin(p)}>
      <div className="pct-bar__label">
        <span className="pct-bar__name" title={label}>
          {label}
        </span>
        {raw ? <span className="pct-bar__raw">{raw}</span> : null}
      </div>
      <div
        className="pct-bar__track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={p}
        aria-valuetext={`${p}th percentile`}
      >
        <div className="pct-bar__fill" style={{ "--pct": p } as CSSProperties} />
      </div>
      <span className="pct-bar__value" aria-hidden="true">
        {p}
      </span>
    </div>
  );
}
