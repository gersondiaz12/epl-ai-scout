import { ClubPicker } from "@/components/club-picker";
import { SampleDataNotice } from "@/components/sample-data-notice";
import { SiteHeader } from "@/components/site-header";
import { getClubs } from "@/lib/sample-data";

export default function Home() {
  const clubs = getClubs();

  return (
    <>
      <SiteHeader />
      <main className="container-page flex-1 py-8 sm:py-12">
        <div className="stack" style={{ "--stack-gap": "2rem" } as React.CSSProperties}>
          <div className="flex max-w-2xl flex-col gap-2">
            <p className="eyebrow">Premier League 2026–27</p>
            <h1 className="text-2xl font-semibold sm:text-3xl">Choose a club to scout</h1>
            <p className="text-fg-muted">
              Pick the club you&apos;re recruiting for. You can switch to another club at any
              time from the header.
            </p>
          </div>

          <ClubPicker clubs={clubs} />

          <SampleDataNotice>
            The 20 clubs are this season&apos;s Premier League line-up. Squads and figures are
            fictional placeholders until real data is connected.
          </SampleDataNotice>
        </div>
      </main>
    </>
  );
}
