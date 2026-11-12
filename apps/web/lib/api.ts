import "server-only";
import { cacheLife, cacheTag } from "next/cache";
import type { ClubDetail, ClubSummary, PlayerProfile, Season } from "./types";

/**
 * Reads football data from apps/api. Server-only: the API URL never reaches
 * the browser. Results are cached for an hour; the data changes only when the
 * ingest runs.
 *
 * Callers render inside <Suspense> after `await connection()`, so `next build`
 * never needs the API to be running.
 */

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** GET a JSON resource. null for 404; throws for anything else unexpected. */
async function get<T>(path: string): Promise<T | null> {
  const response = await fetch(`${API_URL}${path}`, { headers: { accept: "application/json" } });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`API ${response.status} for ${path}`);
  return (await response.json()) as T;
}

async function getRequired<T>(path: string): Promise<T> {
  const data = await get<T>(path);
  if (data === null) throw new Error(`API returned 404 for ${path}`);
  return data;
}

export async function getCurrentSeason(): Promise<Season> {
  "use cache";
  cacheLife("hours");
  cacheTag("football");
  return getRequired<Season>("/seasons/current");
}

export async function getClubs(): Promise<ClubSummary[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("football");
  return getRequired<ClubSummary[]>("/clubs");
}

export async function getClub(slug: string): Promise<ClubDetail | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("football");
  return get<ClubDetail>(`/clubs/${encodeURIComponent(slug)}`);
}

export async function getPlayer(id: string): Promise<PlayerProfile | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("football");
  if (!/^\d+$/.test(id)) return null;
  return get<PlayerProfile>(`/players/${id}`);
}
