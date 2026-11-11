"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { MISSING, formatNumber } from "@/lib/format";
import type { ClubSummary } from "@/lib/types";

type SortKey = "name" | "averageAge" | "topGoals";
type Sort = { key: SortKey; dir: "ascending" | "descending" };

/** Direction a column sorts in when first clicked. */
const FIRST_DIR: Record<SortKey, Sort["dir"]> = {
  name: "ascending",
  averageAge: "ascending",
  topGoals: "descending",
};

function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

function matches(club: ClubSummary, query: string): boolean {
  if (!query) return true;
  return [club.name, club.code, club.city, club.ground].some((field) =>
    normalize(field).includes(query),
  );
}

function sortValue(club: ClubSummary, key: SortKey): number | string | null {
  if (key === "name") return club.name;
  if (key === "averageAge") return club.averageAge;
  return club.topScorer?.goals ?? null;
}

function compare(a: ClubSummary, b: ClubSummary, { key, dir }: Sort): number {
  const va = sortValue(a, key);
  const vb = sortValue(b, key);
  // Missing values always sink to the bottom, whatever the direction.
  if (va === null || vb === null) {
    if (va !== vb) return va === null ? 1 : -1;
  } else if (va !== vb) {
    const order = typeof va === "string" ? va.localeCompare(vb as string) : va - (vb as number);
    return dir === "ascending" ? order : -order;
  }
  return a.name.localeCompare(b.name);
}

function surname(name: string): string {
  const parts = name.split(" ");
  return parts.length > 1 ? parts.slice(1).join(" ") : name;
}

export function ClubPicker({ clubs }: { clubs: ClubSummary[] }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>({ key: "name", dir: "ascending" });
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const countId = useId();

  const q = normalize(query);
  const visible = clubs.filter((club) => matches(club, q)).sort((a, b) => compare(a, b, sort));

  // "/" focuses the search from anywhere on the page, as in most data tools.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement;
      if (target.closest("input, textarea, select, [contenteditable='true']")) return;
      e.preventDefault();
      inputRef.current?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  function sortBy(key: SortKey) {
    setSort((current) =>
      current.key === key
        ? { key, dir: current.dir === "ascending" ? "descending" : "ascending" }
        : { key, dir: FIRST_DIR[key] },
    );
  }

  function ariaSort(key: SortKey) {
    return sort.key === key ? sort.dir : undefined;
  }

  return (
    <section className="panel" aria-labelledby={countId}>
      <div className="panel-header flex-wrap items-center">
        <h2 id={countId} className="font-semibold" aria-live="polite">
          {visible.length === clubs.length ? (
            <>
              {clubs.length} clubs
            </>
          ) : (
            <>
              {visible.length} <span className="font-normal text-fg-muted">of {clubs.length} clubs</span>
            </>
          )}
        </h2>
        <div className="relative w-full sm:w-72">
          <label htmlFor={inputId} className="sr-only">
            Filter clubs by name, code, ground or city
          </label>
          <input
            ref={inputRef}
            id={inputId}
            type="search"
            className="input pr-9"
            placeholder="Filter by name, code or city"
            autoComplete="off"
            spellCheck={false}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && visible.length > 0) {
                router.push(`/clubs/${visible[0].slug}`);
              } else if (e.key === "Escape" && query) {
                e.preventDefault();
                setQuery("");
              }
            }}
            aria-describedby={`${inputId}-hint`}
          />
          {query ? null : (
            <span
              className="kbd pointer-coarse:hidden pointer-events-none absolute top-1/2 right-2 -translate-y-1/2"
              aria-hidden="true"
            >
              /
            </span>
          )}
          <span id={`${inputId}-hint`} className="sr-only">
            Press Enter to open the first club in the list.
          </span>
        </div>
      </div>

      <div className="table-scroll rounded-t-none border-0">
        <table className="data-table data-table--comfortable [--row-h:3rem] max-sm:[--cell-px:0.5rem]">
          <caption className="sr-only">
            Premier League clubs. Select a club to open its squad. Column headers sort the table.
          </caption>
          <thead>
            <tr>
              <th scope="col" aria-sort={ariaSort("name")}>
                <button type="button" className="sort-btn" onClick={() => sortBy("name")}>
                  Club
                </button>
              </th>
              <th scope="col" className="hidden md:table-cell">
                Ground
              </th>
              <th scope="col" className="num max-[22.5rem]:hidden" aria-sort={ariaSort("averageAge")}>
                <button type="button" className="sort-btn" onClick={() => sortBy("averageAge")}>
                  Avg age
                </button>
              </th>
              <th scope="col" className="group-start">
                Top scorer
              </th>
              <th scope="col" className="num" aria-sort={ariaSort("topGoals")}>
                <button
                  type="button"
                  className="sort-btn"
                  onClick={() => sortBy("topGoals")}
                  title="League goals by the club's top scorer"
                >
                  Gls
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((club) => (
              <tr key={club.slug} className="row-link">
                <th scope="row" className="py-1.5 font-normal whitespace-normal sm:whitespace-nowrap">
                  <div className="flex items-center gap-3">
                    <span className="club-code club-code--sm hidden sm:inline-grid" aria-hidden="true">
                      {club.code}
                    </span>
                    <div className="flex min-w-0 flex-col">
                      <Link
                        href={`/clubs/${club.slug}`}
                        className="row-link__target font-medium text-fg"
                      >
                        {club.name}
                      </Link>
                      <span className="flex items-center gap-1.5 text-2xs text-fg-subtle">
                        {club.city}
                        {club.promoted ? (
                          <span className="tag py-0 text-[0.625rem] leading-3.5">Promoted</span>
                        ) : null}
                      </span>
                    </div>
                  </div>
                </th>
                <td className="hidden text-fg-muted md:table-cell">{club.ground}</td>
                <td className="num max-[22.5rem]:hidden">
                  {club.averageAge === null ? MISSING : formatNumber(club.averageAge, 1)}
                </td>
                <td className="group-start">
                  {club.topScorer ? (
                    <>
                      <span className="sm:hidden">{surname(club.topScorer.name)}</span>
                      <span className="hidden sm:inline">{club.topScorer.name}</span>
                    </>
                  ) : (
                    <span className="text-fg-subtle">{MISSING}</span>
                  )}
                </td>
                <td className="num font-semibold">
                  {club.topScorer ? formatNumber(club.topScorer.goals) : MISSING}
                </td>
              </tr>
            ))}
            {visible.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center whitespace-normal text-fg-muted">
                  No club matches “{query}”.{" "}
                  <button type="button" className="link" onClick={() => setQuery("")}>
                    Clear filter
                  </button>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
