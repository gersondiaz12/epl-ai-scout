import Link from "next/link";
import type { ReactNode } from "react";
import { type NavSection, SiteNav } from "@/components/site-nav";
import { formatSeason } from "@/lib/season";

type SiteHeaderProps = {
  /** Season label from the API, e.g. "2026-27". Omitted while loading. */
  season?: string;
  /** The main-nav section this page belongs to, marked as current. */
  current?: NavSection;
  children?: ReactNode;
};

export function SiteHeader({ season, current, children }: SiteHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/90 backdrop-blur">
      <div className="container-page flex h-(--header-h) items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-2 sm:gap-4">
          <Link href="/" className="flex shrink-0 items-baseline gap-2 font-semibold tracking-tight">
            EPL AI Scout
            {season ? (
              <span className="eyebrow hidden sm:inline">{formatSeason(season)}</span>
            ) : null}
          </Link>
          <SiteNav current={current} />
        </div>
        {children ? <div className="flex items-center gap-2">{children}</div> : null}
      </div>
    </header>
  );
}
