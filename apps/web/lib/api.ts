import "server-only";
import { cacheLife, cacheTag } from "next/cache";
import type {
  ClubDetail,
  ClubSummary,
  InForm,
  PlayerProfile,
  PlayerSearchParams,
  PlayerSearchResult,
  Position,
  PositionGroup,
  Season,
} from "./types";
import { SEARCH_LIMIT } from "./types";

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

/** The league's players ranked by FPL form (top 50), ranked by the API. */
export async function getInForm(): Promise<InForm> {
  "use cache";
  cacheLife("hours");
  cacheTag("football");
  return getRequired<InForm>("/in-form?limit=50");
}

/** Every league player whose current position is `position`. */
export async function getPositionGroup(position: Position): Promise<PositionGroup> {
  "use cache";
  cacheLife("hours");
  cacheTag("football");
  return getRequired<PositionGroup>(`/positions/${position}`);
}

/** Players by name (accent-insensitive, matched by the API), position and age range. */
export async function searchPlayers({
  q,
  position,
  minAge,
  maxAge,
}: PlayerSearchParams): Promise<PlayerSearchResult> {
  "use cache";
  cacheLife("hours");
  cacheTag("football");
  const params = new URLSearchParams({ limit: String(SEARCH_LIMIT) });
  if (q) params.set("q", q);
  if (position) params.set("position", position);
  if (minAge !== null) params.set("min_age", String(minAge));
  if (maxAge !== null) params.set("max_age", String(maxAge));
  return getRequired<PlayerSearchResult>(`/players?${params}`);
}
