import { ClubPicker } from "@/components/club-picker";
import { SampleDataNotice } from "@/components/sample-data-notice";
import { SiteHeader } from "@/components/site-header";
import { getClubSummaries } from "@/lib/sample-data";

export default function Home() {
  const clubs = getClubSummaries();

  return (
    <>
      <SiteHeader />
      <main className="container-page flex-1 py-6 sm:py-10">
        <div className="stack [--stack-gap:1.25rem]">
          <header className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold sm:text-2xl">Select a club to scout</h1>
            <p className="max-w-2xl text-fg-muted">
              Premier League 2026–27. Your club sets the squad you scout; change it any time
              from the header.
            </p>
          </header>

          <ClubPicker clubs={clubs} />

          <div className="flex flex-col gap-2">
            <p className="max-w-2xl text-xs text-fg-muted">
              Average age and top scorer are calculated from each club&apos;s listed players.
              Goals are league goals this season.
            </p>
            <SampleDataNotice>
              The 20 clubs are this season&apos;s real line-up. Players and every figure are
              fictional placeholders until real data is connected.
            </SampleDataNotice>
          </div>
        </div>
      </main>
    </>
  );
}
