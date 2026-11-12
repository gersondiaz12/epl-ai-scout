import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { type ReactNode, Suspense } from "react";
import { ClubSwitcher } from "@/components/club-switcher";
import { DataSourceNote } from "@/components/data-source-note";
import { PageLoading } from "@/components/page-loading";
import { SiteHeader } from "@/components/site-header";
import { EmptySlot } from "@/components/ui/empty-slot";
import { PercentileBar } from "@/components/ui/percentile-bar";
import { formatMinutes, formatNumber, formatPer90 } from "@/lib/format";
import { getClubs, getPlayer } from "@/lib/api";
import { formatSeason } from "@/lib/season";
import { POSITION_LABELS, POSITION_NAMES } from "@/lib/types";

export async function generateMetadata({
  params,
}: PageProps<"/players/[id]">): Promise<Metadata> {
  await connection();
  const { id } = await params;
  const player = await getPlayer(id).catch(() => null);
  return { title: player ? `${player.name} · ${player.club.name} · EPL AI Scout` : "EPL AI Scout" };
}

function Fact({ label, children, sub }: { label: string; children: ReactNode; sub?: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
      {sub ? <dd className="facts__sub">{sub}</dd> : null}
    </div>
  );
}

export default function PlayerPage({ params }: PageProps<"/players/[id]">) {
  return (
    <Suspense fallback={<PageLoading label="Loading player…" />}>
      <PlayerContent params={params} />
    </Suspense>
  );
}

async function PlayerContent({ params }: Pick<PageProps<"/players/[id]">, "params">) {
  await connection();
  const { id } = await params;
  const [player, clubs] = await Promise.all([getPlayer(id), getClubs()]);
  if (!player) notFound();

  const { club, totals, percentiles } = player;
  const season = formatSeason(player.season);
  const poolName = POSITION_LABELS[player.position].toLowerCase();
  const moved = player.by_club.length > 1;

  return (
    <>
      <SiteHeader season={player.season}>
        <ClubSwitcher key={club.slug} clubs={clubs} current={club} />
      </SiteHeader>

      <main className="container-page flex-1 py-6 sm:py-10">
        <div className="stack [--stack-gap:1.5rem]">
          <nav aria-label="Breadcrumb" className="text-xs text-fg-muted">
            <Link href="/" className="link-quiet">
              Clubs
            </Link>
            <span aria-hidden="true"> / </span>
            <Link href={`/clubs/${club.slug}`} className="link-quiet">
              {club.name}
            </Link>
            <span aria-hidden="true"> / </span>
            <span className="text-fg">{player.name}</span>
          </nav>

          <header className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold sm:text-2xl">{player.name}</h1>
            <p className="cluster text-fg-muted [--cluster-gap:0.5rem]">
              <span className="pos-badge" data-pos={player.position}>
                {player.position}
              </span>
              <span>
                {POSITION_NAMES[player.position]} ·{" "}
                <Link href={`/clubs/${club.slug}`} className="link">
                  {club.name}
                </Link>
              </span>
            </p>
          </header>

          <dl className="facts grid-cols-2 lg:grid-cols-4">
            <Fact label="Club" sub={club.city}>
              <Link href={`/clubs/${club.slug}`} className="link-quiet block truncate">
                {club.name}
              </Link>
            </Fact>
            <Fact label="Position">
              <span className="flex items-center gap-2">
                <span className="pos-badge" data-pos={player.position}>
                  {player.position}
                </span>
                {POSITION_NAMES[player.position]}
              </span>
            </Fact>
            <Fact label="Age">{formatNumber(player.age)}</Fact>
            <Fact label="League minutes" sub={`${formatNumber(totals.appearances)} appearances`}>
              {formatMinutes(totals.minutes)}
            </Fact>
          </dl>

          {/* Same columns as the "League" group in the squad table. */}
          <section className="panel" aria-labelledby="league-heading">
            <div className="panel-header items-center">
              <h2 id="league-heading" className="font-semibold">
                League {season}
              </h2>
              <p className="text-xs text-fg-muted">
                {moved ? `Season totals across ${player.by_club.length} clubs` : "Season totals"}
              </p>
            </div>
            <dl
              className={`facts grid-cols-2 rounded-none border-0 sm:grid-cols-4 ${moved ? "border-b border-border" : "rounded-t-none"}`}
            >
              <Fact label="Appearances">{formatNumber(totals.appearances)}</Fact>
              <Fact label="Minutes">{formatMinutes(totals.minutes)}</Fact>
              <Fact label="Goals">{formatNumber(totals.goals)}</Fact>
              <Fact label="Assists">{formatNumber(totals.assists)}</Fact>
            </dl>
            {moved ? (
              <div className="table-scroll rounded-t-none border-0">
                <table className="data-table">
                  <caption className="sr-only">League figures by club this season</caption>
                  <thead>
                    <tr>
                      <th scope="col">Club</th>
                      <th scope="col" className="num">
                        Apps
                      </th>
                      <th scope="col" className="num">
                        Mins
                      </th>
                      <th scope="col" className="num">
                        Gls
                      </th>
                      <th scope="col" className="num">
                        Ast
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {player.by_club.map((row) => (
                      <tr key={row.club.slug}>
                        <th scope="row" className="font-medium">
                          <span className="flex items-center gap-2">
                            <Link href={`/clubs/${row.club.slug}`} className="link-quiet">
                              {row.club.name}
                            </Link>
                            <span className="tag">{row.is_current_club ? "Now" : "Left"}</span>
                          </span>
                        </th>
                        <td className="num">{formatNumber(row.appearances)}</td>
                        <td className="num">{formatMinutes(row.minutes)}</td>
                        <td className="num">{formatNumber(row.goals)}</td>
                        <td className="num">{formatNumber(row.assists)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>

          <section className="panel" aria-labelledby="percentiles-heading">
            <div className="panel-header flex-wrap items-center">
              <h2 id="percentiles-heading" className="font-semibold">
                Per 90 percentiles
              </h2>
              <p className="text-xs text-fg-muted">
                vs {formatNumber(percentiles.pool_size)} league {poolName} ·{" "}
                {formatNumber(percentiles.min_minutes)}+ mins · {season}
              </p>
            </div>
            <div className="p-4">
              {percentiles.rows ? (
                <div className="chart-block">
                  <div className="pct-list">
                    {percentiles.rows.map((row) => (
                      <PercentileBar
                        key={row.key}
                        label={row.label}
                        percentile={row.percentile}
                        raw={formatPer90(row.per90)}
                      />
                    ))}
                  </div>
                  <div className="chart-note flex flex-col gap-2">
                    <p>
                      Each bar ranks this player&apos;s rate per 90 minutes against the{" "}
                      {formatNumber(percentiles.pool_size)} Premier League {poolName} with at least{" "}
                      {formatNumber(percentiles.min_minutes)} league minutes this season. Other
                      positions are left out.
                    </p>
                    <p>
                      The number on the right is the percentile: 80 means a better rate than 80% of
                      that group. The tick marks the median. The small figure beside each stat is
                      the raw per-90 rate, from {formatMinutes(totals.minutes)} minutes.
                    </p>
                    {percentiles.rows.some((row) => !row.higher_is_better) ? (
                      <p>
                        For xG conceded, lower is better, so conceding less ranks higher.
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : (
                <p className="max-w-2xl text-fg-muted">
                  Not enough minutes to compare. {player.name} has played{" "}
                  {formatMinutes(totals.minutes)} league minutes; percentiles need at least{" "}
                  {formatNumber(percentiles.min_minutes)}, because rates over a few appearances
                  swing too much to rank fairly.
                </p>
              )}
            </div>
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            {/* TODO: predicted value. Comes from the apps/api valuation model. */}
            <EmptySlot slot="predicted-value" title="Predicted value">
              A model estimate of this player&apos;s value will go here, with the reasons behind
              it.
            </EmptySlot>
            {/* TODO: similar players. Comes from apps/api; same-position players with a close per-90 profile. */}
            <EmptySlot slot="similar-players" title="Similar players">
              Players in the same position with a similar per-90 profile will be listed here.
            </EmptySlot>
          </div>

          <DataSourceNote />
        </div>
      </main>
    </>
  );
}
