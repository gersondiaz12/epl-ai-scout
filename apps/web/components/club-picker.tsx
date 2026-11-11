"use client";

import Link from "next/link";
import { useId, useState } from "react";
import type { Club } from "@/lib/types";

function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

function matches(club: Club, query: string): boolean {
  if (!query) return true;
  return [club.name, club.code, club.city, club.ground].some((field) =>
    normalize(field).includes(query),
  );
}

export function ClubPicker({ clubs }: { clubs: Club[] }) {
  const [query, setQuery] = useState("");
  const inputId = useId();
  const statusId = useId();

  const q = normalize(query);
  const visible = clubs.filter((club) => matches(club, q));

  return (
    <div className="stack" style={{ "--stack-gap": "1rem" } as React.CSSProperties}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex w-full flex-col gap-1 sm:max-w-xs">
          <label htmlFor={inputId} className="eyebrow">
            Find a club
          </label>
          <input
            id={inputId}
            type="search"
            className="input"
            placeholder="Name, code or city"
            autoComplete="off"
            spellCheck={false}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-describedby={statusId}
          />
        </div>
        <p id={statusId} className="text-xs text-fg-subtle" aria-live="polite">
          {visible.length === clubs.length
            ? `${clubs.length} clubs`
            : `${visible.length} of ${clubs.length} clubs`}
        </p>
      </div>

      {visible.length > 0 ? (
        <ul className="grid-auto" style={{ "--grid-min": "15rem", "--grid-gap": "0.5rem" } as React.CSSProperties}>
          {visible.map((club) => (
            <li key={club.slug}>
              <Link href={`/clubs/${club.slug}`} className="club-card">
                <span className="club-code" aria-hidden="true">
                  {club.code}
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-medium">{club.name}</span>
                  <span className="truncate text-xs text-fg-muted">
                    {club.ground} · {club.city}
                  </span>
                </span>
                {club.promoted ? <span className="tag">Promoted</span> : null}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="panel px-4 py-8 text-center text-fg-muted">
          No club matches “{query}”.{" "}
          <button type="button" className="link" onClick={() => setQuery("")}>
            Clear search
          </button>
        </div>
      )}
    </div>
  );
}
