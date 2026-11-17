import { NOT_YET_AVAILABLE } from "@/lib/format";

/** Marks a value the data source doesn't provide yet. Never shows a number. */
export function NotAvailable() {
  return (
    <span className="text-xs font-normal text-fg-subtle" title="The data source doesn't provide this yet">
      {NOT_YET_AVAILABLE}
    </span>
  );
}
