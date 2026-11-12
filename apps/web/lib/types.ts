/**
 * Response shapes from apps/api. These mirror apps/api/app/schemas.py; keep
 * the two in step. Field names stay snake_case, as the API sends them.
 */

export type Position = "GK" | "DEF" | "MID" | "FWD";

export const POSITIONS: readonly Position[] = ["GK", "DEF", "MID", "FWD"];

export const POSITION_LABELS: Record<Position, string> = {
  GK: "Goalkeepers",
  DEF: "Defenders",
  MID: "Midfielders",
  FWD: "Forwards",
};

export const POSITION_NAMES: Record<Position, string> = {
  GK: "Goalkeeper",
  DEF: "Defender",
  MID: "Midfielder",
  FWD: "Forward",
};

export type Season = {
  label: string; // "2026-27"
  start_date: string;
  end_date: string;
  per90_min_minutes: number;
};

export type ClubSummary = {
  slug: string;
  name: string;
  /** Three-letter code used as a text identity mark (no crests). */
  short_name: string;
  ground: string | null;
  city: string | null;
  promoted: boolean;
  squad_size: number;
  average_age: number | null;
  top_scorer: { player_id: number; name: string; goals: number } | null;
};

/** Rates per 90 minutes; null when the player is under the minutes threshold. */
export type Per90 = {
  ga: number | null;
  xg: number | null;
  xa: number | null;
  saves: number | null;
  xg_conceded: number | null;
};

export type SquadPlayer = {
  player_id: number;
  name: string;
  position: Position;
  age: number | null;
  /** False when the player has since left; the row holds their stats for this club. */
  is_current_club: boolean;
  appearances: number;
  minutes: number;
  goals: number;
  assists: number;
  per90: Per90;
};

export type ClubDetail = Omit<ClubSummary, "squad_size" | "average_age" | "top_scorer"> & {
  season: string;
  per90_min_minutes: number;
  squad: SquadPlayer[];
};

export type ClubRef = { slug: string; name: string; short_name: string; city: string | null };

export type SeasonTotals = {
  appearances: number;
  minutes: number;
  goals: number;
  assists: number;
};

export type PercentileRow = {
  key: string;
  label: string;
  per90: number;
  percentile: number;
  higher_is_better: boolean;
};

export type PlayerProfile = {
  id: number;
  name: string;
  display_name: string;
  birth_date: string | null;
  age: number | null;
  position: Position;
  season: string;
  club: ClubRef;
  totals: SeasonTotals;
  by_club: (SeasonTotals & { club: ClubRef; is_current_club: boolean })[];
  per90: Per90;
  percentiles: {
    pool_size: number;
    min_minutes: number;
    /** null when the player is under min_minutes. */
    rows: PercentileRow[] | null;
  };
};
