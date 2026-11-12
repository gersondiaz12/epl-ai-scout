import { connection } from "next/server";
import { Suspense } from "react";
import { ClubPicker } from "@/components/club-picker";
import { DataSourceNote } from "@/components/data-source-note";
import { PageLoading } from "@/components/page-loading";
import { SiteHeader } from "@/components/site-header";
import { getClubs, getCurrentSeason } from "@/lib/api";
import { formatSeason } from "@/lib/season";

export default function Home() {
  return (
    <Suspense fallback={<PageLoading label="Loading clubs…" />}>
      <HomeContent />
    </Suspense>
  );
}

async function HomeContent() {
  await connection(); // read at request time, so the build never needs the API
  const [season, clubs] = await Promise.all([getCurrentSeason(), getClubs()]);

  return (
    <>
      <SiteHeader season={season.label} />
      <main className="container-page flex-1 py-6 sm:py-10">
        <div className="stack [--stack-gap:1.25rem]">
          <header className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold sm:text-2xl">Select a club to scout</h1>
            <p className="max-w-2xl text-fg-muted">
              Premier League {formatSeason(season.label)}. Your club sets the squad you scout;
              change it any time from the header.
            </p>
          </header>

          <ClubPicker clubs={clubs} />

          <DataSourceNote>
            Average age is for each club&apos;s current squad. Top scorer counts league goals for
            that club this season.
          </DataSourceNote>
        </div>
      </main>
    </>
  );
}
