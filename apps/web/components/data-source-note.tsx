import type { ReactNode } from "react";

/** Says where a page's figures come from, so every number is traceable. */
export function DataSourceNote({ children }: { children?: ReactNode }) {
  return (
    <p className="max-w-3xl text-xs text-fg-subtle">
      {children ? <>{children} </> : null}
      Source: Fantasy Premier League, Premier League matches only.
    </p>
  );
}
