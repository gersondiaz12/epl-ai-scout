import { SiteHeader } from "@/components/site-header";

/** Suspense fallback while a page's data loads from the API. */
export function PageLoading({ label }: { label: string }) {
  return (
    <>
      <SiteHeader />
      <main className="container-page flex-1 py-6 sm:py-10" aria-busy="true">
        <p className="text-fg-muted" role="status">
          {label}
        </p>
      </main>
    </>
  );
}
