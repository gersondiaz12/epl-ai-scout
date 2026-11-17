import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { DataSourceNote } from "@/components/data-source-note";
import { PageLoading } from "@/components/page-loading";
import { PlayerSearchForm } from "@/components/player-search-form";
import { PlayerSearchTable } from "@/components/player-search-table";
import { SiteHeader } from "@/components/site-header";
import { formatNumber } from "@/lib/format";
import { searchPlayers } from "@/lib/api";
import {
  POSITION_LABELS,
  POSITIONS,
  SEARCH_AGE_MAX,
  SEARCH_AGE_MIN,
  type PlayerSearchParams,
  type Position,
} from "@/lib/types";

export const metadata: Metadata = { title: "Player search · EPL AI Scout" };

type RawParams = Awaited<PageProps<"/players">["searchParams"]>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** URL params to a valid search, plus any problems to show instead of results. */
function parseSearch(raw: RawParams) {
  const values = {
    q: first(raw.q).slice(0, 100),
    position: first(raw.position).toUpperCase(),
    minAge: first(raw.min_age),
    maxAge: first(raw.max_age),
  };
  const problems: string[] = [];
  const age = (text: string, label: string): number | null => {
    if (text === "") return null;
    const n = Number(text);
    if (!Number.isInteger(n) || n < SEARCH_AGE_MIN || n > SEARCH_AGE_MAX) {
      problems.push(`${label} age must be a whole number from ${SEARCH_AGE_MIN} to ${SEARCH_AGE_MAX}.`);
      return null;
    }
    return n;
  };
  const minAge = age(values.minAge, "Minimum");
  const maxAge = age(values.maxAge, "Maximum");
  if (minAge !== null && maxAge !== null && minAge > maxAge) {
    problems.push("Minimum age is higher than maximum age.");
  }
  const position = (POSITIONS as readonly string[]).includes(values.position)
    ? (values.position as Position)
    : null;
  if (values.position && !position) values.position = "";
  const search: PlayerSearchParams = { q: values.q, position, minAge, maxAge };
  return { values, search, problems };
}

export default function PlayerSearchPage({ searchParams }: PageProps<"/players">) {
  return (
    <Suspense fallback={<PageLoading label="Searching players…" />}>
      <SearchContent searchParams={searchParams} />
    </Suspense>
  );
}

async function SearchContent({ searchParams }: Pick<PageProps<"/players">, "searchParams">) {
  await connection(); // read at request time, so the build never needs the API
  const { values, search, problems } = parseSearch(await searchParams);
  const result = problems.length ? null : await searchPlayers(search);
  const ageFiltered = search.minAge !== null || search.maxAge !== null;

  return (
    <>
      <SiteHeader season={result?.season} current="search" />

      <main className="container-page flex-1 py-6 sm:py-10">
        <div className="stack [--stack-gap:1.5rem]">
          <nav aria-label="Breadcrumb" className="text-xs text-fg-muted">
            <Link href="/" className="link-quiet">
              Clubs
            </Link>
            <span aria-hidden="true"> / </span>
            <span className="text-fg">Player search</span>
          </nav>

          <header className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold sm:text-2xl">Player search</h1>
            <p className="max-w-2xl text-fg-muted">
              Find any Premier League player by name, position and age.
            </p>
          </header>

          <PlayerSearchForm values={values} active={search} />

          {problems.length ? (
            <section className="panel p-4" role="alert">
              <p className="font-medium">Check the age range</p>
              <ul className="mt-1 list-disc pl-5 text-fg-muted">
                {problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </section>
          ) : result && result.players.length ? (
            <PlayerSearchTable
              players={result.players}
              total={result.total}
              season={result.season}
              hasQuery={search.q !== ""}
            />
          ) : (
            <section className="panel p-4" aria-live="polite">
              <p className="font-medium">No players match</p>
              <p className="mt-1 max-w-2xl text-fg-muted">
                {search.q ? <>Nothing for &ldquo;{search.q}&rdquo;</> : "Nothing"}
                {search.position ? ` among ${POSITION_LABELS[search.position].toLowerCase()}` : ""}
                {ageFiltered ? " in that age range" : ""}. Check the spelling or widen the
                filters.
              </p>
            </section>
          )}

          <div className="flex flex-col gap-2">
            <p className="max-w-3xl text-xs text-fg-muted">
              <strong className="font-medium text-fg">How to read this.</strong> Names match
              without accents or punctuation, and every word you type must appear in the name.
              Position is FPL&apos;s current one; the club is the player&apos;s current club, and
              league figures are season totals across all their clubs. Age filters include both
              ends of the range.
              {result && ageFiltered && result.unknown_age_excluded > 0
                ? ` ${formatNumber(result.unknown_age_excluded)} ${
                    result.unknown_age_excluded === 1 ? "player matches" : "players match"
                  } otherwise but ${
                    result.unknown_age_excluded === 1 ? "has" : "have"
                  } no birth date in FPL, so ${
                    result.unknown_age_excluded === 1 ? "is" : "are"
                  } left out of age-filtered results.`
                : null}
            </p>
            <DataSourceNote />
          </div>
        </div>
      </main>
    </>
  );
}
