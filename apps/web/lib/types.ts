export type Position = "GK" | "DEF" | "MID" | "FWD";

export const POSITIONS: readonly Position[] = ["GK", "DEF", "MID", "FWD"];

export type Club = {
  slug: string;
  name: string;
  /** Three-letter code used as a text identity mark (no crests). */
  code: string;
  ground: string;
  city: string;
  /** Promoted from the Championship for this season. */
  promoted: boolean;
};

export type Player = {
  id: string;
  name: string;
  position: Position;
  age: number;
  /** League minutes this season. */
  minutes: number;
};
