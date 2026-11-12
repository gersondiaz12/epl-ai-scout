import type { ReactNode } from "react";

type EmptySlotProps = {
  /** Stable id for the future feature; also set as data-slot so it's easy to find. */
  slot: string;
  title: string;
  /** What will go here. Plain text only: an empty slot never shows numbers. */
  children: ReactNode;
};

/** Reserved, clearly labelled space for a feature that isn't built yet. */
export function EmptySlot({ slot, title, children }: EmptySlotProps) {
  const headingId = `${slot}-heading`;
  return (
    <section className="panel panel--slot" data-slot={slot} aria-labelledby={headingId}>
      <div className="panel-header items-center">
        <h2 id={headingId} className="font-semibold text-fg-muted">
          {title}
        </h2>
        <span className="tag">Not built yet</span>
      </div>
      <p className="px-4 py-6 text-fg-subtle">{children}</p>
    </section>
  );
}
