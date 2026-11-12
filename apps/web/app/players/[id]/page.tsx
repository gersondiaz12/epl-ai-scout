import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { ClubSwitcher } from "@/components/club-switcher";
import { SampleDataNotice } from "@/components/sample-data-notice";
import { SiteHeader } from "@/components/site-header";
import { EmptySlot } from "@/components/ui/empty-slot";
import { PercentileBar } from "@/components/ui/percentile-bar";
import {
  formatMarketValue,
  formatMinutes,
  formatMonthYear,
  formatNumber,
  formatPer90,
} from "@/lib/format";
import { PER90_MIN_MINUTES } from "@/lib/per90";
import {
  getAllPlayers,
  getClubs,
  getPlayer,
  getPlayerPercentiles,
} from "@/lib/sample-data";
import { SEASON_LABEL, isFinalContractYear } from "@/lib/season";
import { POSITION_LABELS, POSITION_NAMES } from "@/lib/types";

export function generateStaticParams() {
  return getAllPlayers().map((player) => ({ id: player.id }));
}

export async function generateMetadata({
  params,
}: PageProps<"/players/[id]">): Promise<Metadata> {
  const { id } = await params;
  const found = getPlayer(id);
  return {
    title: found
      ? `${found.player.name} · ${found.club.name} · EPL AI Scout`
      : "Player not found · EPL AI Scout",
  };
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

export default async function PlayerPage({ params }: PageProps<"/players/[id]">) {
  const { id } = await params;
  const found = getPlayer(id);
  if (!found) notFound();

  const { player, club } = found;
  const { poolSize, rows } = getPlayerPercentiles(player);
  const poolName = POSITION_LABELS[player.position].toLowerCase();
  const finalYear = isFinalContractYear(player.contractExpiry);

  return (
    <>
      <SiteHeader>
        <ClubSwitcher key={club.slug} clubs={getClubs()} current={club} />
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

          <dl className="facts grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
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
            <Fact label="League minutes" sub={`${formatNumber(player.appearances)} appearances`}>
              {formatMinutes(player.minutes)}
            </Fact>
            <Fact
              label="Contract expires"
              sub={finalYear ? <span className="tag">Final year</span> : null}
            >
              {formatMonthYear(player.contractExpiry)}
            </Fact>
            <Fact label="Market value" sub="Fictional sample, EUR">
              {formatMarketValue(player.marketValue)}
            </Fact>
          </dl>

          {/* Same columns as the "League" group in the squad table. */}
          <section className="panel" aria-labelledby="league-heading">
            <div className="panel-header items-center">
              <h2 id="league-heading" className="font-semibold">
                League {SEASON_LABEL}
              </h2>
              <p className="text-xs text-fg-muted">Season totals</p>
            </div>
            <dl className="facts grid-cols-2 rounded-t-none border-0 sm:grid-cols-4">
              <Fact label="Appearances">{formatNumber(player.appearances)}</Fact>
              <Fact label="Minutes">{formatMinutes(player.minutes)}</Fact>
              <Fact label="Goals">{formatNumber(player.goals)}</Fact>
              <Fact label="Assists">{formatNumber(player.assists)}</Fact>
            </dl>
          </section>

          <section className="panel" aria-labelledby="percentiles-heading">
            <div className="panel-header flex-wrap items-center">
              <h2 id="percentiles-heading" className="font-semibold">
                Per 90 percentiles
              </h2>
              <p className="text-xs text-fg-muted">
                vs {formatNumber(poolSize)} league {poolName} ·{" "}
                {formatNumber(PER90_MIN_MINUTES)}+ mins · {SEASON_LABEL}
              </p>
            </div>
            <div className="p-4">
              {rows ? (
                <div className="chart-block">
                  <div className="pct-list">
                    {rows.map((row) => (
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
                      {formatNumber(poolSize)} Premier League {poolName} with at least{" "}
                      {formatNumber(PER90_MIN_MINUTES)} league minutes this season. Other
                      positions are left out.
                    </p>
                    <p>
                      The number on the right is the percentile: 80 means a higher rate than 80%
                      of that group. The tick marks the median. The small figure beside each stat
                      is the raw per-90 rate, from {formatMinutes(player.minutes)} minutes.
                    </p>
                    {player.position === "GK" ? (
                      <p>
                        Goalkeeping metrics such as saves and goals prevented aren&apos;t in the
                        sample data yet, so only progressive actions are compared.
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : (
                <p className="max-w-2xl text-fg-muted">
                  Not enough minutes to compare. {player.name} has played{" "}
                  {formatMinutes(player.minutes)} league minutes; percentiles need at least{" "}
                  {formatNumber(PER90_MIN_MINUTES)}, because rates over a few appearances swing
                  too much to rank fairly.
                </p>
              )}
            </div>
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            {/* TODO: predicted value. Comes from the apps/api valuation model; shown beside market value. */}
            <EmptySlot slot="predicted-value" title="Predicted value">
              A model estimate of this player&apos;s value will go here, next to the market value,
              with the reasons behind it.
            </EmptySlot>
            {/* TODO: similar players. Comes from apps/api; same-position players with a close per-90 profile. */}
            <EmptySlot slot="similar-players" title="Similar players">
              Players in the same position with a similar per-90 profile will be listed here.
            </EmptySlot>
          </div>

          <SampleDataNotice>
            This player and every figure on this page, including market value and percentiles,
            are fictional placeholders.
          </SampleDataNotice>
        </div>
      </main>
    </>
  );
}
