import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { DataSourceNote } from "@/components/data-source-note";
import { InFormTable } from "@/components/in-form-table";
import { PageLoading } from "@/components/page-loading";
import { SiteHeader } from "@/components/site-header";
import { NotAvailable } from "@/components/ui/not-available";
import { formatDate, formatNumber } from "@/lib/format";
import { getInForm } from "@/lib/api";
import { formatSeason } from "@/lib/season";

export const metadata: Metadata = { title: "In form · EPL AI Scout" };

export default function InFormPage() {
  return (
    <Suspense fallback={<PageLoading label="Loading in-form players…" />}>
      <InFormContent />
    </Suspense>
  );
}

async function InFormContent() {
  await connection(); // read at request time, so the build never needs the API
  const inForm = await getInForm();
  const season = formatSeason(inForm.season);

  return (
    <>
      <SiteHeader season={inForm.season} current="in-form" />

      <main className="container-page flex-1 py-6 sm:py-10">
        <div className="stack [--stack-gap:1.5rem]">
          <nav aria-label="Breadcrumb" className="text-xs text-fg-muted">
            <Link href="/" className="link-quiet">
              Clubs
            </Link>
            <span aria-hidden="true"> / </span>
            <span className="text-fg">In form</span>
          </nav>

          <header className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold sm:text-2xl">In form</h1>
            <p className="max-w-2xl text-fg-muted">
              Premier League {season} players ranked by FPL form. Form as of{" "}
              {inForm.form_updated_at ? formatDate(inForm.form_updated_at) : <NotAvailable />}.
            </p>
          </header>

          {inForm.players.length ? (
            <InFormTable players={inForm.players} poolSize={inForm.pool_size} season={inForm.season} />
          ) : (
            <section className="panel p-4">
              <p className="max-w-2xl text-fg-muted">
                No players to rank yet. Form is not yet available for any player with{" "}
                {formatNumber(inForm.min_minutes)}+ league minutes; it arrives with the next FPL
                data load.
              </p>
            </section>
          )}

          <div className="flex flex-col gap-2">
            <p className="max-w-3xl text-xs text-fg-muted">
              <strong className="font-medium text-fg">How to read this.</strong>{" "}
              <em className="not-italic">Form</em> is Fantasy Premier League&apos;s own figure: a
              player&apos;s average FPL points per match over the last 30 days. It can be
              negative. Only players with at least {formatNumber(inForm.min_minutes)} league
              minutes this season are ranked, so one good cameo can&apos;t top the list. Equal
              form shares a rank, with more minutes listed first. League and per-90 columns are
              season totals across all the player&apos;s clubs.
              {inForm.without_form > 0
                ? ` ${formatNumber(inForm.without_form)} players with enough minutes have no form figure from FPL and aren't ranked.`
                : null}
            </p>
            <DataSourceNote />
          </div>
        </div>
      </main>
    </>
  );
}
