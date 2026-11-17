"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

const LINKS = [
  { section: "in-form", href: "/in-form", label: "In form" },
  { section: "positions", href: "/positions", label: "Positions" },
  { section: "search", href: "/players", label: "Search" },
] as const;

export type NavSection = (typeof LINKS)[number]["section"];

/**
 * Main navigation. Inline links from the sm breakpoint; on phones they fold
 * into a menu so the header still fits beside the club switcher at 320px.
 * The menu is a <details> (works before hydration), with the same
 * close-on-outside-click and Escape handling as the club switcher. Each page
 * renders its own header, so the menu starts closed after navigating.
 */
export function SiteNav({ current }: { current?: NavSection }) {
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
    <>
      <nav aria-label="Main" className="hidden items-baseline gap-3 text-sm sm:flex">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`link-quiet whitespace-nowrap ${link.section === current ? "font-medium" : "text-fg-muted"}`}
            aria-current={link.section === current ? "page" : undefined}
          >
            {link.label}
          </Link>
        ))}
      </nav>

      <details ref={ref} className="menu sm:hidden">
        <summary className="btn btn-ghost btn-sm">
          Menu
          <span aria-hidden="true" className="text-fg-subtle">
            ▾
          </span>
        </summary>
        <nav aria-label="Main" className="menu__panel right-auto left-0 w-44">
          <ul>
            {LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="menu__item"
                  aria-current={link.section === current ? "page" : undefined}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </details>
    </>
  );
}
