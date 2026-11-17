"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { NotAvailable } from "@/components/ui/not-available";
import { SortHeader } from "@/components/ui/sort-header";
import { formatMinutes, formatNumber } from "@/lib/format";
import { formatSeason } from "@/lib/season";
import { compareValues, nextSort, type SortDir, type SortState } from "@/lib/sort";
import type { PlayerSearchRow } from "@/lib/types";

/** "match" keeps the API's order: best name match first, then most minutes. */
type SortKey = "match" | "name" | "club" | "age" | "apps" | "mins" | "goals" | "assists";
type ColumnKey = Exclude<SortKey, "match">;

const COLUMNS: Record<
  ColumnKey,
  {
    label: string;
    title: string;
    first: SortDir;
    value: (r: PlayerSearchRow) => number | string | null;
  }
> = {
  name: { label: "Name", title: "Name", first: "ascending", value: (r) => r.name },
  club: { label: "Club", title: "Club", first: "ascending", value: (r) => r.club.name },
  age: { label: "Age", title: "Age", first: "ascending", value: (r) => r.age },
  apps: { label: "Apps", title: "Appearances", first: "descending", value: (r) => r.appearances },
  mins: { label: "Mins", title: "Minutes", first: "descending", value: (r) => r.minutes },
  goals: { label: "Gls", title: "Goals", first: "descending", value: (r) => r.goals },
  assists: { label: "Ast", title: "Assists", first: "descending", value: (r) => r.assists },
};

const COLUMN_KEYS = Object.keys(COLUMNS) as ColumnKey[];
const MATCH_SORT: SortState<SortKey> = { key: "match", dir: "ascending" };

function sortRows(rows: PlayerSearchRow[], sort: SortState<SortKey>): PlayerSearchRow[] {
  if (sort.key === "match") return rows;
  const value = COLUMNS[sort.key].value;
  const apiOrder = new Map(rows.map((r, i) => [r.player_id, i]));
  return rows.toSorted(
    (a, b) =>
      compareValues(value(a), value(b), sort.dir) ||
      (apiOrder.get(a.player_id) ?? 0) - (apiOrder.get(b.player_id) ?? 0),
  );
}

type PlayerSearchTableProps = {
  players: PlayerSearchRow[];
  total: number;
  season: string;
  /** True when a name was searched, so "best match" ordering means something. */
  hasQuery: boolean;
};

export function PlayerSearchTable({ players, total, season, hasQuery }: PlayerSearchTableProps) {
  const [sort, setSort] = useState<SortState<SortKey>>(MATCH_SORT);
  const sortSelectId = useId();
  const rows = sortRows(players, sort);
  const matchLabel = hasQuery ? "Best match" : "Minutes (default)";

  const onSort = (key: ColumnKey) =>
    setSort((s) => nextSort(s, key, COLUMNS[key].first) as SortState<SortKey>);
  const header = (key: ColumnKey, className = "num") => (
    <SortHeader
      sortKey={key}
      sort={sort as SortState<ColumnKey>}
      onSort={onSort}
      label={COLUMNS[key].label}
      title={COLUMNS[key].title}
      className={className}
    />
  );

  return (
    <section className="panel" aria-labelledby="results-heading">
      <div className="panel-header flex-wrap items-center">
        <h2 id="results-heading" className="font-semibold" aria-live="polite">
          {formatNumber(total)} {total === 1 ? "player" : "players"}
          {total > players.length ? (
            <span className="font-normal text-fg-muted">
              {" "}
              · showing the first {formatNumber(players.length)}
            </span>
          ) : null}
        </h2>
        <div className="flex w-full min-w-0 items-center gap-1.5 sm:w-auto">
          <label htmlFor={sortSelectId} className="text-xs text-fg-muted">
            Sort
          </label>
          <select
            id={sortSelectId}
            className="input h-8 min-w-0 flex-1 py-0 pr-2 pl-2 text-xs sm:w-48 sm:flex-none"
            value={sort.key}
            onChange={(e) => {
              const key = e.target.value as SortKey;
              setSort(key === "match" ? MATCH_SORT : { key, dir: COLUMNS[key].first });
            }}
          >
            <option value="match">{matchLabel}</option>
            {COLUMN_KEYS.map((key) => (
              <option key={key} value={key}>
                {COLUMNS[key].title}
              </option>
            ))}
          </select>
          {sort.key === "match" ? null : (
            <button
              type="button"
              className="btn btn-secondary btn-sm md:hidden"
              onClick={() =>
                setSort((s) => ({ ...s, dir: s.dir === "ascending" ? "descending" : "ascending" }))
              }
              aria-label={`Sort direction: ${sort.dir}. Switch direction.`}
            >
              {sort.dir === "ascending" ? "Low–high" : "High–low"}
            </button>
          )}
        </div>
      </div>

      <div className="table-scroll table-scroll--sticky-header rounded-t-none border-0">
        <table className="data-table">
          <caption className="sr-only">
            Player search results,{" "}
            {sort.key === "match"
              ? matchLabel.toLowerCase()
              : `sorted by ${COLUMNS[sort.key].title.toLowerCase()} (${sort.dir})`}
            . Column headers change the sort.
          </caption>
          <thead>
            <tr>
              <th scope="colgroup" colSpan={3}>
                Player
              </th>
              <th scope="colgroup" colSpan={4} className="group-start">
                League {formatSeason(season)}
              </th>
            </tr>
            <tr>
              {header("name", "col-sticky")}
              {header("club", "")}
              {header("age")}
              {header("apps", "num group-start")}
              {header("mins")}
              {header("goals")}
              {header("assists")}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.player_id}>
                <th scope="row" className="col-sticky font-medium">
                  <span className="flex items-center gap-2">
                    <Link
                      href={`/players/${r.player_id}`}
                      className="link-quiet max-w-[9.5rem] truncate sm:max-w-none"
                      title={r.name}
                    >
                      {r.name}
                    </Link>
                    <span className="pos-badge" data-pos={r.position}>
                      {r.position}
                    </span>
                  </span>
                </th>
                <td>
                  <Link href={`/clubs/${r.club.slug}`} className="link-quiet" title={r.club.name}>
                    <span className="lg:hidden">{r.club.short_name}</span>
                    <span className="hidden lg:inline">{r.club.name}</span>
                  </Link>
                </td>
                <td className="num">{r.age === null ? <NotAvailable /> : formatNumber(r.age)}</td>
                <td className="num group-start">{formatNumber(r.appearances)}</td>
                <td className="num">{formatMinutes(r.minutes)}</td>
                <td className="num">{formatNumber(r.goals)}</td>
                <td className="num">{formatNumber(r.assists)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
