"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { SortHeader } from "@/components/ui/sort-header";
import { formatMinutes, formatNumber, formatPer90 } from "@/lib/format";
import { formatSeason } from "@/lib/season";
import { compareValues, nextSort, type SortDir, type SortState } from "@/lib/sort";
import type { InFormPlayer } from "@/lib/types";

type SortKey =
  | "rank"
  | "name"
  | "club"
  | "form"
  | "apps"
  | "mins"
  | "goals"
  | "assists"
  | "ga90"
  | "xg90"
  | "xa90";

/** Every sortable column: header text, full name, first-click direction and value. */
const COLUMNS: Record<
  SortKey,
  { label: string; title: string; first: SortDir; value: (r: InFormPlayer) => number | string | null }
> = {
  rank: { label: "#", title: "Form rank", first: "ascending", value: (r) => r.rank },
  name: { label: "Name", title: "Name", first: "ascending", value: (r) => r.name },
  club: { label: "Club", title: "Club", first: "ascending", value: (r) => r.club.name },
  form: { label: "Form", title: "FPL form", first: "descending", value: (r) => r.form },
  apps: { label: "Apps", title: "Appearances", first: "descending", value: (r) => r.appearances },
  mins: { label: "Mins", title: "Minutes", first: "descending", value: (r) => r.minutes },
  goals: { label: "Gls", title: "Goals", first: "descending", value: (r) => r.goals },
  assists: { label: "Ast", title: "Assists", first: "descending", value: (r) => r.assists },
  ga90: { label: "G+A", title: "Goals plus assists per 90", first: "descending", value: (r) => r.per90.ga },
  xg90: { label: "xG", title: "Expected goals per 90", first: "descending", value: (r) => r.per90.xg },
  xa90: { label: "xA", title: "Expected assists per 90", first: "descending", value: (r) => r.per90.xa },
};

const SORT_KEYS = Object.keys(COLUMNS) as SortKey[];

function sortRows(rows: InFormPlayer[], sort: SortState<SortKey>): InFormPlayer[] {
  const value = COLUMNS[sort.key].value;
  // Ties fall back to the API's order (form, then minutes), so the ranking stays the anchor.
  const apiOrder = new Map(rows.map((r, i) => [r.player_id, i]));
  return rows.toSorted(
    (a, b) =>
      compareValues(value(a), value(b), sort.dir) ||
      (apiOrder.get(a.player_id) ?? 0) - (apiOrder.get(b.player_id) ?? 0),
  );
}

type InFormTableProps = {
  players: InFormPlayer[];
  poolSize: number;
  season: string;
};

export function InFormTable({ players, poolSize, season }: InFormTableProps) {
  const [sort, setSort] = useState<SortState<SortKey>>({ key: "rank", dir: "ascending" });
  const sortSelectId = useId();
  const rows = sortRows(players, sort);

  const onSort = (key: SortKey) => setSort((s) => nextSort(s, key, COLUMNS[key].first));
  const header = (key: SortKey, className = "num") => (
    <SortHeader
      sortKey={key}
      sort={sort}
      onSort={onSort}
      label={COLUMNS[key].label}
      title={COLUMNS[key].title}
      className={className}
    />
  );

  return (
    <section className="panel" aria-labelledby="in-form-heading">
      <div className="panel-header flex-wrap items-center">
        <h2 id="in-form-heading" className="font-semibold">
          Top {formatNumber(players.length)}{" "}
          <span className="font-normal text-fg-muted">
            of {formatNumber(poolSize)} ranked players
          </span>
        </h2>
        {/* Headers scroll out of view on phones, so offer the same sort as a menu. */}
        <div className="flex w-full min-w-0 items-center gap-1.5 sm:w-auto md:hidden">
          <label htmlFor={sortSelectId} className="text-xs text-fg-muted">
            Sort
          </label>
          <select
            id={sortSelectId}
            className="input h-8 min-w-0 flex-1 py-0 pr-2 pl-2 text-xs sm:w-56 sm:flex-none"
            value={sort.key}
            onChange={(e) => {
              const key = e.target.value as SortKey;
              setSort({ key, dir: COLUMNS[key].first });
            }}
          >
            {SORT_KEYS.map((key) => (
              <option key={key} value={key}>
                {COLUMNS[key].title}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() =>
              setSort((s) => ({ ...s, dir: s.dir === "ascending" ? "descending" : "ascending" }))
            }
            aria-label={`Sort direction: ${sort.dir}. Switch direction.`}
          >
            {sort.dir === "ascending" ? "Low–high" : "High–low"}
          </button>
        </div>
      </div>

      <div className="table-scroll table-scroll--sticky-header rounded-t-none border-0">
        <table className="data-table">
          <caption className="sr-only">
            Premier League players by FPL form, sorted by {COLUMNS[sort.key].title.toLowerCase()} (
            {sort.dir}). Column headers change the sort.
          </caption>
          <thead>
            <tr>
              <th scope="colgroup" colSpan={4}>
                Player
              </th>
              <th scope="colgroup" colSpan={4} className="group-start">
                League {formatSeason(season)}
              </th>
              <th scope="colgroup" colSpan={3} className="group-start">
                Per 90
              </th>
            </tr>
            <tr>
              {header("rank")}
              {header("name", "col-sticky")}
              {header("club", "")}
              {header("form")}
              {header("apps", "num group-start")}
              {header("mins")}
              {header("goals")}
              {header("assists")}
              {header("ga90", "num group-start")}
              {header("xg90")}
              {header("xa90")}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.player_id}>
                <td className="num text-fg-muted">{formatNumber(r.rank)}</td>
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
                <td className="num font-semibold">{formatNumber(r.form, 1)}</td>
                <td className="num group-start">{formatNumber(r.appearances)}</td>
                <td className="num">{formatMinutes(r.minutes)}</td>
                <td className="num">{formatNumber(r.goals)}</td>
                <td className="num">{formatNumber(r.assists)}</td>
                <td className="num group-start">{formatPer90(r.per90.ga)}</td>
                <td className="num">{formatPer90(r.per90.xg)}</td>
                <td className="num">{formatPer90(r.per90.xa)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
