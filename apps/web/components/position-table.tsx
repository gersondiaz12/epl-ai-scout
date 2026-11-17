"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { SortHeader } from "@/components/ui/sort-header";
import { formatMinutes, formatNumber, formatPer90 } from "@/lib/format";
import { formatSeason } from "@/lib/season";
import { compareValues, nextSort, type SortDir, type SortState } from "@/lib/sort";
import { POSITION_LABELS, type Position, type PositionPlayer } from "@/lib/types";

type SortKey = "name" | "club" | "apps" | "mins" | "ga90" | "xg90" | "xa90" | "saves90" | "xgc90";

/** Every sortable column: header text, full name, first-click direction and value. */
const COLUMNS: Record<
  SortKey,
  { label: string; title: string; first: SortDir; value: (r: PositionPlayer) => number | string | null }
> = {
  name: { label: "Name", title: "Name", first: "ascending", value: (r) => r.name },
  club: { label: "Club", title: "Club", first: "ascending", value: (r) => r.club.name },
  apps: { label: "Apps", title: "Appearances", first: "descending", value: (r) => r.appearances },
  mins: { label: "Mins", title: "Minutes", first: "descending", value: (r) => r.minutes },
  ga90: { label: "G+A", title: "Goals plus assists per 90", first: "descending", value: (r) => r.per90.ga },
  xg90: { label: "xG", title: "Expected goals per 90", first: "descending", value: (r) => r.per90.xg },
  xa90: { label: "xA", title: "Expected assists per 90", first: "descending", value: (r) => r.per90.xa },
  saves90: { label: "Svs", title: "Saves per 90", first: "descending", value: (r) => r.per90.saves },
  // Lower is better, so the first click shows the best (fewest conceded) first.
  xgc90: { label: "xGC", title: "xG conceded per 90", first: "ascending", value: (r) => r.per90.xg_conceded },
};

const SORT_KEYS = Object.keys(COLUMNS) as SortKey[];

function sortRows(rows: PositionPlayer[], sort: SortState<SortKey>): PositionPlayer[] {
  const value = COLUMNS[sort.key].value;
  return rows.toSorted(
    (a, b) =>
      compareValues(value(a), value(b), sort.dir) ||
      b.minutes - a.minutes ||
      a.name.localeCompare(b.name),
  );
}

type PositionTableProps = {
  players: PositionPlayer[];
  position: Position;
  season: string;
};

export function PositionTable({ players, position, season }: PositionTableProps) {
  const [sort, setSort] = useState<SortState<SortKey>>({ key: "mins", dir: "descending" });
  const sortSelectId = useId();
  const rows = sortRows(players, sort);
  const groupName = POSITION_LABELS[position].toLowerCase();

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
    <section className="panel" aria-labelledby="position-heading">
      <div className="panel-header flex-wrap items-center">
        <h2 id="position-heading" className="font-semibold">
          {POSITION_LABELS[position]}{" "}
          <span className="font-normal text-fg-muted">· {formatNumber(players.length)} players</span>
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
            Premier League {groupName}, sorted by {COLUMNS[sort.key].title.toLowerCase()} (
            {sort.dir}). Column headers change the sort.
          </caption>
          <thead>
            <tr>
              <th scope="colgroup" colSpan={2}>
                Player
              </th>
              <th scope="colgroup" colSpan={2} className="group-start">
                League {formatSeason(season)}
              </th>
              <th scope="colgroup" colSpan={5} className="group-start">
                Per 90
              </th>
            </tr>
            <tr>
              {header("name", "col-sticky")}
              {header("club", "")}
              {header("apps", "num group-start")}
              {header("mins")}
              {header("ga90", "num group-start")}
              {header("xg90")}
              {header("xa90")}
              {header("saves90")}
              {header("xgc90")}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.player_id}>
                <th scope="row" className="col-sticky font-medium">
                  <Link
                    href={`/players/${r.player_id}`}
                    className="link-quiet block max-w-[9.5rem] truncate sm:max-w-none"
                    title={r.name}
                  >
                    {r.name}
                  </Link>
                </th>
                <td>
                  <Link href={`/clubs/${r.club.slug}`} className="link-quiet" title={r.club.name}>
                    <span className="lg:hidden">{r.club.short_name}</span>
                    <span className="hidden lg:inline">{r.club.name}</span>
                  </Link>
                </td>
                <td className="num group-start">{formatNumber(r.appearances)}</td>
                <td className="num">{formatMinutes(r.minutes)}</td>
                <td className="num group-start">{formatPer90(r.per90.ga)}</td>
                <td className="num">{formatPer90(r.per90.xg)}</td>
                <td className="num">{formatPer90(r.per90.xa)}</td>
                <td className="num">{formatPer90(r.per90.saves)}</td>
                <td className="num">{formatPer90(r.per90.xg_conceded)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
