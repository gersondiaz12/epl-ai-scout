"use client";

import { useId, useState } from "react";
import { SortHeader } from "@/components/ui/sort-header";
import { formatMinutes, formatMonthYear, formatNumber, formatPer90 } from "@/lib/format";
import { per90 } from "@/lib/per90";
import { SEASON_LABEL, isFinalContractYear } from "@/lib/season";
import { compareValues, nextSort, type SortDir, type SortState } from "@/lib/sort";
import { POSITION_LABELS, POSITIONS, type Player } from "@/lib/types";

type SortKey =
  | "name"
  | "age"
  | "contract"
  | "apps"
  | "mins"
  | "goals"
  | "assists"
  | "ga90"
  | "xg90"
  | "prog90";

type Row = Player & { ga90: number | null; xg90: number | null; prog90: number | null };

/** Every sortable column: header text, full name, first-click direction and value. */
const COLUMNS: Record<SortKey, { label: string; title: string; first: SortDir; value: (r: Row) => number | string | null }> = {
  name: { label: "Name", title: "Name", first: "ascending", value: (r) => r.name },
  age: { label: "Age", title: "Age", first: "ascending", value: (r) => r.age },
  contract: { label: "Contract", title: "Contract expiry", first: "ascending", value: (r) => r.contractExpiry },
  apps: { label: "Apps", title: "Appearances", first: "descending", value: (r) => r.appearances },
  mins: { label: "Mins", title: "Minutes", first: "descending", value: (r) => r.minutes },
  goals: { label: "Gls", title: "Goals", first: "descending", value: (r) => r.goals },
  assists: { label: "Ast", title: "Assists", first: "descending", value: (r) => r.assists },
  ga90: { label: "G+A", title: "Goals plus assists per 90", first: "descending", value: (r) => r.ga90 },
  xg90: { label: "xG", title: "Expected goals per 90", first: "descending", value: (r) => r.xg90 },
  prog90: { label: "Prog", title: "Progressive actions per 90", first: "descending", value: (r) => r.prog90 },
};

const SORT_KEYS = Object.keys(COLUMNS) as SortKey[];
const COLUMN_COUNT = SORT_KEYS.length;

function toRow(p: Player): Row {
  return {
    ...p,
    ga90: per90(p.goals + p.assists, p.minutes),
    xg90: per90(p.xg, p.minutes),
    prog90: per90(p.progressiveActions, p.minutes),
  };
}

function sortRows(rows: Row[], sort: SortState<SortKey>): Row[] {
  const value = COLUMNS[sort.key].value;
  return rows.toSorted(
    (a, b) =>
      compareValues(value(a), value(b), sort.dir) ||
      b.minutes - a.minutes ||
      a.name.localeCompare(b.name),
  );
}

export function SquadTable({ players, clubName }: { players: Player[]; clubName: string }) {
  const [sort, setSort] = useState<SortState<SortKey>>({ key: "mins", dir: "descending" });
  const [grouped, setGrouped] = useState(true);
  const groupToggleId = useId();
  const sortSelectId = useId();

  const rows = sortRows(players.map(toRow), sort);
  const groups = grouped
    ? POSITIONS.map((pos) => ({ pos, rows: rows.filter((r) => r.position === pos) })).filter(
        (g) => g.rows.length > 0,
      )
    : [{ pos: null, rows }];

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

  const totalGoals = players.reduce((sum, p) => sum + p.goals, 0);
  const totalAssists = players.reduce((sum, p) => sum + p.assists, 0);

  return (
    <section className="panel" aria-labelledby="squad-heading">
      <div className="panel-header flex-wrap items-center">
        <h2 id="squad-heading" className="font-semibold">
          Squad <span className="font-normal text-fg-muted">· {formatNumber(players.length)} players</span>
        </h2>
        <div className="cluster w-full [--cluster-gap:0.75rem] md:w-auto">
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
          <label htmlFor={groupToggleId} className="flex items-center gap-1.5 text-xs text-fg-muted">
            <input
              id={groupToggleId}
              type="checkbox"
              className="size-4 accent-[var(--fg)]"
              checked={grouped}
              onChange={(e) => setGrouped(e.target.checked)}
            />
            Group by position
          </label>
        </div>
      </div>

      <div className="table-scroll table-scroll--sticky-header rounded-t-none border-0">
        <table className="data-table">
          <caption className="sr-only">
            {clubName} squad{grouped ? ", grouped by position" : ""}, sorted by{" "}
            {COLUMNS[sort.key].title.toLowerCase()} ({sort.dir}). Column headers change the sort.
          </caption>
          <thead>
            <tr>
              <th scope="colgroup" colSpan={3}>
                Player
              </th>
              <th scope="colgroup" colSpan={4} className="group-start">
                League {SEASON_LABEL}
              </th>
              <th scope="colgroup" colSpan={3} className="group-start">
                Per 90
              </th>
            </tr>
            <tr>
              {header("name", "col-sticky")}
              {header("age")}
              {header("contract")}
              {header("apps", "num group-start")}
              {header("mins")}
              {header("goals")}
              {header("assists")}
              {header("ga90", "num group-start")}
              {header("xg90")}
              {header("prog90")}
            </tr>
          </thead>

          {groups.map((group) => (
            <tbody key={group.pos ?? "all"}>
              {group.pos ? (
                <tr className="group-row">
                  <th scope="rowgroup" colSpan={COLUMN_COUNT}>
                    <span className="sticky left-2 inline-flex items-center gap-2">
                      <span className="pos-badge" data-pos={group.pos}>
                        {group.pos}
                      </span>
                      {POSITION_LABELS[group.pos]}
                      <span className="font-normal text-fg-subtle">{group.rows.length}</span>
                    </span>
                  </th>
                </tr>
              ) : null}
              {group.rows.map((r) => (
                <PlayerRow key={r.id} row={r} showPosition={!grouped} />
              ))}
            </tbody>
          ))}

          <tfoot>
            <tr>
              <th scope="row" colSpan={3}>
                Squad total
              </th>
              <td className="group-start" colSpan={2} />
              <td className="num">{formatNumber(totalGoals)}</td>
              <td className="num">{formatNumber(totalAssists)}</td>
              <td className="group-start" colSpan={3} />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

function PlayerRow({ row: r, showPosition }: { row: Row; showPosition: boolean }) {
  const finalYear = isFinalContractYear(r.contractExpiry);
  return (
    <tr>
      <th scope="row" className="col-sticky font-medium">
        <span className="flex items-center gap-2">
          <span className="max-w-[9.5rem] truncate sm:max-w-none" title={r.name}>
            {r.name}
          </span>
          {showPosition ? (
            <span className="pos-badge" data-pos={r.position}>
              {r.position}
            </span>
          ) : null}
        </span>
      </th>
      <td className="num">{formatNumber(r.age)}</td>
      <td className="num">
        {finalYear ? <span className="tag mr-1.5">Final yr</span> : null}
        {formatMonthYear(r.contractExpiry)}
      </td>
      <td className="num group-start">{formatNumber(r.appearances)}</td>
      <td className="num">{formatMinutes(r.minutes)}</td>
      <td className="num">{formatNumber(r.goals)}</td>
      <td className="num">{formatNumber(r.assists)}</td>
      <td className="num group-start">{formatPer90(r.ga90)}</td>
      <td className="num">{formatPer90(r.xg90)}</td>
      <td className="num">{formatPer90(r.prog90)}</td>
    </tr>
  );
}
