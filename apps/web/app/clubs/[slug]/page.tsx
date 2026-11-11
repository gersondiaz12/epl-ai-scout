import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ClubSwitcher } from "@/components/club-switcher";
import { SampleDataNotice } from "@/components/sample-data-notice";
import { SiteHeader } from "@/components/site-header";
import { StatChip } from "@/components/ui/stat-chip";
import { formatMinutes, formatNumber } from "@/lib/format";
import { getClub, getClubs, getSquad } from "@/lib/sample-data";
import { POSITIONS } from "@/lib/types";

export function generateStaticParams() {
  return getClubs().map((club) => ({ slug: club.slug }));
}

export async function generateMetadata({
  params,
}: PageProps<"/clubs/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const club = getClub(slug);
  return { title: club ? `${club.name} · EPL AI Scout` : "Club not found · EPL AI Scout" };
}

export default async function ClubPage({ params }: PageProps<"/clubs/[slug]">) {
  const { slug } = await params;
  const club = getClub(slug);
  if (!club) notFound();

  const squad = getSquad(club.slug).toSorted(
    (a, b) =>
      POSITIONS.indexOf(a.position) - POSITIONS.indexOf(b.position) || b.minutes - a.minutes,
  );

  return (
    <>
      <SiteHeader>
        <ClubSwitcher key={club.slug} clubs={getClubs()} current={club} />
      </SiteHeader>

      <main className="container-page flex-1 py-8 sm:py-10">
        <div className="stack" style={{ "--stack-gap": "2rem" } as React.CSSProperties}>
          <nav aria-label="Breadcrumb" className="text-xs text-fg-muted">
            <Link href="/" className="link-quiet">
              Clubs
            </Link>
            <span aria-hidden="true"> / </span>
            <span className="text-fg">{club.name}</span>
          </nav>

          <div className="flex items-center gap-4">
            <span className="club-code h-12 w-16 text-sm" aria-hidden="true">
              {club.code}
            </span>
            <div className="flex min-w-0 flex-col gap-1">
              <h1 className="text-2xl font-semibold sm:text-3xl">{club.name}</h1>
              <p className="cluster text-fg-muted" style={{ "--cluster-gap": "0.5rem" } as React.CSSProperties}>
                <span>
                  {club.ground} · {club.city}
                </span>
                {club.promoted ? <span className="tag">Promoted 2026</span> : null}
              </p>
            </div>
          </div>

          <section className="panel" aria-labelledby="squad-heading">
            <div className="panel-header flex-wrap">
              <h2 id="squad-heading" className="font-semibold">
                Squad
              </h2>
              <div className="cluster" style={{ "--cluster-gap": "0.375rem" } as React.CSSProperties}>
                <StatChip label="Players" value={formatNumber(squad.length)} />
                {POSITIONS.map((pos) => (
                  <StatChip
                    key={pos}
                    label={pos}
                    value={formatNumber(squad.filter((p) => p.position === pos).length)}
                  />
                ))}
              </div>
            </div>
            <div className="table-scroll rounded-t-none border-0">
              <table className="data-table">
                <caption className="sr-only">
                  {club.name} squad, sorted by position then league minutes
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="col-sticky">
                      Player
                    </th>
                    <th scope="col">Pos</th>
                    <th scope="col" className="num">
                      Age
                    </th>
                    <th scope="col" className="num">
                      League mins
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {squad.map((player) => (
                    <tr key={player.id}>
                      <th scope="row" className="col-sticky font-medium">
                        {player.name}
                      </th>
                      <td>
                        <span className="pos-badge" data-pos={player.position}>
                          {player.position}
                        </span>
                      </td>
                      <td className="num">{formatNumber(player.age)}</td>
                      <td className="num">{formatMinutes(player.minutes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <SampleDataNotice>
            Players, ages and minutes on this page are fictional placeholders, not real{" "}
            {club.name} data.
          </SampleDataNotice>
        </div>
      </main>
    </>
  );
}
