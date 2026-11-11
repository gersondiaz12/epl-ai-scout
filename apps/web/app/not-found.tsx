import Link from "next/link";
import { SiteHeader } from "@/components/site-header";

export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="container-page flex-1 py-16">
        <div className="flex max-w-xl flex-col gap-3">
          <p className="eyebrow">Not found</p>
          <h1 className="text-2xl font-semibold">We couldn&apos;t find that page</h1>
          <p className="text-fg-muted">
            The club may not be in this season&apos;s Premier League, or the link is mistyped.
          </p>
          <div>
            <Link href="/" className="btn btn-primary">
              Choose a club
            </Link>
          </div>
        </div>
      </main>
    </>
  );
}
