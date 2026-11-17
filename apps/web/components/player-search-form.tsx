import Form from "next/form";
import Link from "next/link";
import {
  POSITION_LABELS,
  POSITIONS,
  SEARCH_AGE_MAX,
  SEARCH_AGE_MIN,
  type PlayerSearchParams,
} from "@/lib/types";

type PlayerSearchFormProps = {
  /** What the URL asked for, echoed back so the fields show the current search. */
  values: { q: string; position: string; minAge: string; maxAge: string };
  active: PlayerSearchParams;
};

/**
 * A GET form: the search lives in the URL, so results can be shared and the
 * form works before (or without) JavaScript. next/form adds client-side
 * navigation on submit.
 */
export function PlayerSearchForm({ values, active }: PlayerSearchFormProps) {
  const filtered =
    active.q !== "" || active.position !== null || active.minAge !== null || active.maxAge !== null;

  return (
    <Form action="/players" className="panel p-4" role="search" aria-label="Players">
      <div className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_auto_auto_auto]">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="player-search-q" className="text-xs text-fg-muted">
            Name
          </label>
          <input
            id="player-search-q"
            name="q"
            type="search"
            className="input"
            defaultValue={values.q}
            placeholder="e.g. Odegaard"
            maxLength={100}
            autoComplete="off"
            spellCheck={false}
            aria-describedby="player-search-q-hint"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="player-search-position" className="text-xs text-fg-muted">
            Position
          </label>
          <select
            id="player-search-position"
            name="position"
            className="input sm:w-44"
            defaultValue={values.position}
          >
            <option value="">All positions</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {POSITION_LABELS[p]}
              </option>
            ))}
          </select>
        </div>

        <fieldset className="flex flex-col gap-1.5 sm:col-span-2 lg:col-span-1">
          <legend className="mb-1.5 text-xs text-fg-muted">Age</legend>
          <div className="flex items-center gap-2">
            <label htmlFor="player-search-min-age" className="sr-only">
              Minimum age
            </label>
            <input
              id="player-search-min-age"
              name="min_age"
              type="number"
              inputMode="numeric"
              min={SEARCH_AGE_MIN}
              max={SEARCH_AGE_MAX}
              step={1}
              className="input num w-20"
              defaultValue={values.minAge}
              placeholder="Min"
            />
            <span aria-hidden="true" className="text-fg-subtle">
              to
            </span>
            <label htmlFor="player-search-max-age" className="sr-only">
              Maximum age
            </label>
            <input
              id="player-search-max-age"
              name="max_age"
              type="number"
              inputMode="numeric"
              min={SEARCH_AGE_MIN}
              max={SEARCH_AGE_MAX}
              step={1}
              className="input num w-20"
              defaultValue={values.maxAge}
              placeholder="Max"
            />
          </div>
        </fieldset>

        <div className="flex gap-2 sm:col-span-2 lg:col-span-1">
          <button type="submit" className="btn btn-primary h-9">
            Search
          </button>
          {filtered ? (
            <Link href="/players" className="btn btn-ghost h-9">
              Clear
            </Link>
          ) : null}
        </div>
      </div>
      <p id="player-search-q-hint" className="mt-2 text-xs text-fg-subtle">
        Accents optional: &ldquo;Odegaard&rdquo; finds Ødegaard.
      </p>
    </Form>
  );
}
