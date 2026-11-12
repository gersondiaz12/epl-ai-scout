"use client"; // Error boundaries must be Client Components

import { SiteHeader } from "@/components/site-header";

/** Shown when a page can't load its data, most often because the API is down. */
export default function Error({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <>
      <SiteHeader />
      <main className="container-page flex-1 py-16">
        <div className="flex max-w-xl flex-col gap-3">
          <p className="eyebrow">Data unavailable</p>
          <h1 className="text-2xl font-semibold">We couldn&apos;t load this page&apos;s data</h1>
          <p className="text-fg-muted">
            The football data service didn&apos;t respond. Try again in a moment.
          </p>
          <div>
            <button type="button" className="btn btn-primary" onClick={() => retry()}>
              Try again
            </button>
          </div>
        </div>
      </main>
    </>
  );
}
