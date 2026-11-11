import type { ReactNode } from "react";
import { IS_SAMPLE_DATA } from "@/lib/sample-data";

/** Flags placeholder data until the API serves real rows. Delete with lib/sample-data.ts. */
export function SampleDataNotice({ children }: { children: ReactNode }) {
  if (!IS_SAMPLE_DATA) return null;
  return (
    <p className="flex items-start gap-2 text-xs text-fg-muted">
      <span className="tag">Sample data</span>
      <span>{children}</span>
    </p>
  );
}
