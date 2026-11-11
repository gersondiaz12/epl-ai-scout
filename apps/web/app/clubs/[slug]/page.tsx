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
  const totalGoals = squad.reduce((sum, p) => sum + p.goals, 0);
  const totalAssists = squad.reduce((sum, p) => sum + p.assists, 0);

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
            <span className="text-fg">{club.name}</span>
          </nav>

          <header className="flex items-center gap-4">
            <span className="club-code h-12 w-16 text-sm" aria-hidden="true">
              {club.code}
            </span>
            <div className="flex min-w-0 flex-col gap-1">
              <h1 className="text-xl font-semibold sm:text-2xl">{club.name}</h1>
              <p className="cluster text-fg-muted [--cluster-gap:0.5rem]">
                <span>
                  {club.ground} · {club.city}
                </span>
                {club.promoted ? <span className="tag">Promoted 2026</span> : null}
              </p>
            </div>
          </header>

          <section className="panel" aria-labelledby="squad-heading">
            <div className="panel-header flex-wrap items-center">
              <h2 id="squad-heading" className="font-semibold">
                Squad
              </h2>
              <div className="cluster [--cluster-gap:0.375rem]">
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
                  {club.name} squad with league appearances, minutes, goals and assists this
                  season, sorted by position then minutes
                </caption>
                <thead>
                  <tr>
                    <th scope="colgroup" colSpan={3}>
                      Player
                    </th>
                    <th scope="colgroup" colSpan={4} className="group-start">
                      League 2026–27
                    </th>
                  </tr>
                  <tr>
                    <th scope="col" className="col-sticky">
                      Name
                    </th>
                    <th scope="col">Pos</th>
                    <th scope="col" className="num">
                      Age
                    </th>
                    <th scope="col" className="num group-start">
                      <abbr title="Appearances" className="no-underline">
                        Apps
                      </abbr>
                    </th>
                    <th scope="col" className="num">
                      Mins
                    </th>
                    <th scope="col" className="num">
                      <abbr title="Goals" className="no-underline">
                        Gls
                      </abbr>
                    </th>
                    <th scope="col" className="num">
                      <abbr title="Assists" className="no-underline">
                        Ast
                      </abbr>
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
                      <td className="num group-start">{formatNumber(player.appearances)}</td>
                      <td className="num">{formatMinutes(player.minutes)}</td>
                      <td className="num">{formatNumber(player.goals)}</td>
                      <td className="num">{formatNumber(player.assists)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row" colSpan={3}>
                      Squad total
                    </th>
                    <td className="group-start" colSpan={2} />
                    <td className="num">{formatNumber(totalGoals)}</td>
                    <td className="num">{formatNumber(totalAssists)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </section>

          <SampleDataNotice>
            Players, ages, appearances, minutes, goals and assists on this page are fictional
            placeholders, not real {club.name} data.
          </SampleDataNotice>
        </div>
      </main>
    </>
  );
}
