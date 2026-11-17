import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { Suspense } from "react";
import { DataSourceNote } from "@/components/data-source-note";
import { PageLoading } from "@/components/page-loading";
import { PositionTable } from "@/components/position-table";
import { SiteHeader } from "@/components/site-header";
import { formatNumber } from "@/lib/format";
import { getPositionGroup } from "@/lib/api";
import { formatSeason } from "@/lib/season";
import { POSITION_LABELS, POSITION_NAMES, POSITIONS, type Position } from "@/lib/types";

/** URL segment ("gk") to position ("GK"); null for anything else. */
function parsePosition(segment: string): Position | null {
  const upper = segment.toUpperCase();
  return (POSITIONS as readonly string[]).includes(upper) && segment === segment.toLowerCase()
    ? (upper as Position)
    : null;
}

export async function generateMetadata({
  params,
}: PageProps<"/positions/[pos]">): Promise<Metadata> {
  const { pos } = await params;
  const position = parsePosition(pos);
  return { title: position ? `${POSITION_LABELS[position]} · EPL AI Scout` : "EPL AI Scout" };
}

export default function PositionPage({ params }: PageProps<"/positions/[pos]">) {
  return (
    <Suspense fallback={<PageLoading label="Loading players…" />}>
      <PositionContent params={params} />
    </Suspense>
  );
}

async function PositionContent({ params }: Pick<PageProps<"/positions/[pos]">, "params">) {
  await connection(); // read at request time, so the build never needs the API
  const { pos } = await params;
  const position = parsePosition(pos);
  if (!position) notFound();
  const group = await getPositionGroup(position);

  return (
    <>
      <SiteHeader season={group.season} />

      <main className="container-page flex-1 py-6 sm:py-10">
        <div className="stack [--stack-gap:1.5rem]">
          <nav aria-label="Breadcrumb" className="text-xs text-fg-muted">
            <Link href="/" className="link-quiet">
              Clubs
            </Link>
            <span aria-hidden="true"> / </span>
            <span>Positions</span>
            <span aria-hidden="true"> / </span>
            <span className="text-fg">{POSITION_LABELS[position]}</span>
          </nav>

          <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="flex flex-col gap-1">
              <h1 className="text-xl font-semibold sm:text-2xl">{POSITION_LABELS[position]}</h1>
              <p className="max-w-2xl text-fg-muted">
                Every Premier League {formatSeason(group.season)}{" "}
                {POSITION_NAMES[position].toLowerCase()} in one list, by FPL&apos;s current
                position.
              </p>
            </div>
            <nav aria-label="Position" className="cluster [--cluster-gap:0.375rem]">
              {POSITIONS.map((p) => (
                <Link
                  key={p}
                  href={`/positions/${p.toLowerCase()}`}
                  className={`btn btn-sm ${p === position ? "btn-secondary" : "btn-ghost"}`}
                  aria-current={p === position ? "page" : undefined}
                >
                  <span className="pos-badge" data-pos={p}>
                    {p}
                  </span>
                  {POSITION_LABELS[p]}
                </Link>
              ))}
            </nav>
          </header>

          <PositionTable players={group.players} position={position} season={group.season} />

          <div className="flex flex-col gap-2">
            <p className="max-w-3xl text-xs text-fg-muted">
              <strong className="font-medium text-fg">How to read this.</strong> Per-90 figures
              are season totals divided by minutes played, times 90, across every club the player
              has played for this season. They are left blank (–) for players under{" "}
              {formatNumber(group.min_minutes)} minutes and sort last.{" "}
              <em className="not-italic">Svs</em> is saves and{" "}
              <em className="not-italic">xGC</em> is expected goals conceded while the player was
              on the pitch, where lower is better. The club shown is the player&apos;s current
              one.
            </p>
            <DataSourceNote />
          </div>
        </div>
      </main>
    </>
  );
}
