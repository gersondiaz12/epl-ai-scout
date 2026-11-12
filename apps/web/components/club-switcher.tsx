"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import type { ClubRef } from "@/lib/types";

type Club = Pick<ClubRef, "slug" | "name" | "short_name">;

type ClubSwitcherProps = {
  clubs: Club[];
  current: Club;
};

/**
 * Change club from any club page. Built on <details> so it works before
 * hydration; JS adds close-on-outside-click and Escape.
 * Render with key={current.slug} so it resets closed after each switch.
 */
export function ClubSwitcher({ clubs, current }: ClubSwitcherProps) {
  const ref = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    const details = ref.current;
    if (!details) return;

    const close = (focusSummary: boolean) => {
      if (!details.open) return;
      details.open = false;
      if (focusSummary) details.querySelector("summary")?.focus();
    };
    const onPointerDown = (e: PointerEvent) => {
      if (!details.contains(e.target as Node)) close(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close(true);
    };

    document.addEventListener("pointerdown", onPointerDown);
    details.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      details.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  return (
    <details ref={ref} className="menu">
      <summary className="btn btn-secondary" aria-label={`Change club, current: ${current.name}`}>
        <span className="font-mono text-xs font-semibold">{current.short_name}</span>
        <span className="hidden sm:inline">Change club</span>
        <span aria-hidden="true" className="text-fg-subtle">
          ▾
        </span>
      </summary>
      <nav className="menu__panel" aria-label="Premier League clubs">
        <ul>
          {clubs.map((club) => (
            <li key={club.slug}>
              <Link
                href={`/clubs/${club.slug}`}
                className="menu__item"
                aria-current={club.slug === current.slug ? "page" : undefined}
                onClick={() => {
                  if (ref.current) ref.current.open = false;
                }}
              >
                <span className="w-8 font-mono text-xs text-fg-subtle">{club.short_name}</span>
                <span className="truncate">{club.name}</span>
              </Link>
            </li>
          ))}
        </ul>
        <div className="mt-1 border-t border-border pt-1">
          <Link href="/" className="menu__item text-fg-muted">
            View all clubs
          </Link>
        </div>
      </nav>
    </details>
  );
}
