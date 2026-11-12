import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { Suspense } from "react";
import { ClubSwitcher } from "@/components/club-switcher";
import { DataSourceNote } from "@/components/data-source-note";
import { PageLoading } from "@/components/page-loading";
import { SiteHeader } from "@/components/site-header";
import { SquadTable } from "@/components/squad-table";
import { StatChip } from "@/components/ui/stat-chip";
import { formatNumber } from "@/lib/format";
import { getClub, getClubs } from "@/lib/api";

export async function generateMetadata({
  params,
}: PageProps<"/clubs/[slug]">): Promise<Metadata> {
  await connection();
  const { slug } = await params;
  const club = await getClub(slug).catch(() => null);
  return { title: club ? `${club.name} · EPL AI Scout` : "EPL AI Scout" };
}

export default function ClubPage({ params }: PageProps<"/clubs/[slug]">) {
  return (
    <Suspense fallback={<PageLoading label="Loading squad…" />}>
      <ClubContent params={params} />
    </Suspense>
  );
}

async function ClubContent({ params }: Pick<PageProps<"/clubs/[slug]">, "params">) {
  await connection();
  const { slug } = await params;
  const [club, clubs] = await Promise.all([getClub(slug), getClubs()]);
  if (!club) notFound();

  const squad = club.squad.filter((p) => p.is_current_club);
  const ages = squad.flatMap((p) => (p.age === null ? [] : [p.age]));
  const averageAge = ages.length ? ages.reduce((sum, a) => sum + a, 0) / ages.length : null;
  const under21 = ages.filter((a) => a < 21).length;
  const playersUsed = club.squad.filter((p) => p.appearances > 0).length;

  return (
    <>
      <SiteHeader season={club.season}>
        <ClubSwitcher key={club.slug} clubs={clubs} current={club} />
      </SiteHeader>

      <main className="container-page flex-1 py-6 sm:py-10">
        <div className="stack [--stack-gap:1.5rem]">
          <nav aria-label="Breadcrumb" className="text-xs text-fg-muted">
            <Link href="/" className="link-quiet">
              Clubs
            </Link>
            <span aria-hidden="true"> / </span>
            <span className="text-fg">{club.name}</span>
          </nav>

          <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="flex items-center gap-4">
              <span className="club-code h-12 w-16 text-sm" aria-hidden="true">
                {club.short_name}
              </span>
              <div className="flex min-w-0 flex-col gap-1">
                <h1 className="text-xl font-semibold sm:text-2xl">{club.name}</h1>
                <p className="cluster text-fg-muted [--cluster-gap:0.5rem]">
                  {club.ground || club.city ? (
                    <span>{[club.ground, club.city].filter(Boolean).join(" · ")}</span>
                  ) : null}
                  {club.promoted ? <span className="tag">Promoted</span> : null}
                </p>
              </div>
            </div>
            <div className="cluster [--cluster-gap:0.375rem]">
              <StatChip
                label="Avg age"
                value={averageAge === null ? null : formatNumber(averageAge, 1)}
              />
              <StatChip label="Under 21" value={formatNumber(under21)} />
              <StatChip label="Players used" value={formatNumber(playersUsed)} />
            </div>
          </header>

          <SquadTable players={club.squad} clubName={club.name} season={club.season} />

          <div className="flex flex-col gap-2">
            <p className="max-w-3xl text-xs text-fg-muted">
              <strong className="font-medium text-fg">How to read this.</strong> Per-90 figures
              are season totals divided by minutes played, times 90. They are left blank (–) for
              players under {formatNumber(club.per90_min_minutes)} minutes, where one goal can look
              like a star rate. <em className="not-italic">G+A</em> is goals plus assists,{" "}
              <em className="not-italic">xG</em> is expected goals and{" "}
              <em className="not-italic">xA</em> is expected assists. Players marked
              &ldquo;Left&rdquo; have moved on; their figures are for this club only. Average age
              and under-21s count the current squad.
            </p>
            <DataSourceNote />
          </div>
        </div>
      </main>
    </>
  );
}
