/**
 * TEMPORARY SAMPLE DATA. Delete this file once apps/api serves real data,
 * then point the imports of getClubs/getClub/getSquad/getClubSummaries at the
 * API client.
 *
 * Clubs are the real 2026–27 Premier League line-up. Every player and every
 * figure below (age, appearances, minutes, goals, assists) is FICTIONAL and
 * must never be presented as real.
 */
import type { Club, ClubSummary, Player, Position } from "./types";

export const IS_SAMPLE_DATA = true;

/** Sample season state: matchweeks played so far (caps appearances and minutes). */
export const SAMPLE_MATCHWEEKS = 11;

const CLUBS: Club[] = [
  { slug: "arsenal", name: "Arsenal", code: "ARS", ground: "Emirates Stadium", city: "London", promoted: false },
  { slug: "aston-villa", name: "Aston Villa", code: "AVL", ground: "Villa Park", city: "Birmingham", promoted: false },
  { slug: "bournemouth", name: "Bournemouth", code: "BOU", ground: "Vitality Stadium", city: "Bournemouth", promoted: false },
  { slug: "brentford", name: "Brentford", code: "BRE", ground: "Gtech Community Stadium", city: "London", promoted: false },
  { slug: "brighton", name: "Brighton & Hove Albion", code: "BHA", ground: "American Express Stadium", city: "Brighton", promoted: false },
  { slug: "chelsea", name: "Chelsea", code: "CHE", ground: "Stamford Bridge", city: "London", promoted: false },
  { slug: "coventry-city", name: "Coventry City", code: "COV", ground: "Coventry Building Society Arena", city: "Coventry", promoted: true },
  { slug: "crystal-palace", name: "Crystal Palace", code: "CRY", ground: "Selhurst Park", city: "London", promoted: false },
  { slug: "everton", name: "Everton", code: "EVE", ground: "Hill Dickinson Stadium", city: "Liverpool", promoted: false },
  { slug: "fulham", name: "Fulham", code: "FUL", ground: "Craven Cottage", city: "London", promoted: false },
  { slug: "hull-city", name: "Hull City", code: "HUL", ground: "MKM Stadium", city: "Hull", promoted: true },
  { slug: "ipswich-town", name: "Ipswich Town", code: "IPS", ground: "Portman Road", city: "Ipswich", promoted: true },
  { slug: "leeds-united", name: "Leeds United", code: "LEE", ground: "Elland Road", city: "Leeds", promoted: false },
  { slug: "liverpool", name: "Liverpool", code: "LIV", ground: "Anfield", city: "Liverpool", promoted: false },
  { slug: "manchester-city", name: "Manchester City", code: "MCI", ground: "Etihad Stadium", city: "Manchester", promoted: false },
  { slug: "manchester-united", name: "Manchester United", code: "MUN", ground: "Old Trafford", city: "Manchester", promoted: false },
  { slug: "newcastle-united", name: "Newcastle United", code: "NEW", ground: "St James' Park", city: "Newcastle", promoted: false },
  { slug: "nottingham-forest", name: "Nottingham Forest", code: "NFO", ground: "City Ground", city: "Nottingham", promoted: false },
  { slug: "sunderland", name: "Sunderland", code: "SUN", ground: "Stadium of Light", city: "Sunderland", promoted: false },
  { slug: "tottenham-hotspur", name: "Tottenham Hotspur", code: "TOT", ground: "Tottenham Hotspur Stadium", city: "London", promoted: false },
];

/** Fictional players: [name, position, age, appearances, minutes, goals, assists]. */
type Row = [string, Position, number, number, number, number, number];

const SQUADS: Record<string, Row[]> = {
  arsenal: [
    ["Tomas Varga", "GK", 27, 11, 990, 0, 0],
    ["Elliot Marsh", "DEF", 24, 11, 945, 1, 2],
    ["Kofi Mensah", "MID", 22, 10, 812, 3, 4],
    ["Rui Saldanha", "FWD", 26, 10, 703, 6, 2],
    ["Owen Pryce", "DEF", 30, 6, 410, 0, 1],
  ],
  "aston-villa": [
    ["Marek Dvorak", "GK", 31, 11, 990, 0, 0],
    ["Jamal Okafor", "DEF", 25, 10, 900, 1, 0],
    ["Luca Benedetti", "MID", 28, 10, 866, 2, 5],
    ["Sam Whitlock", "FWD", 21, 9, 534, 4, 1],
    ["Harvey Lane", "MID", 19, 4, 122, 0, 0],
  ],
  bournemouth: [
    ["Pieter Smit", "GK", 29, 11, 990, 0, 0],
    ["Callum Reid", "DEF", 23, 10, 871, 0, 2],
    ["Yassine Amrani", "MID", 24, 10, 790, 3, 2],
    ["Diego Ferraz", "FWD", 27, 9, 655, 5, 1],
    ["Noah Ellison", "DEF", 20, 5, 318, 0, 0],
  ],
  brentford: [
    ["Anders Holm", "GK", 26, 10, 900, 0, 0],
    ["Ben Ashworth", "DEF", 28, 11, 990, 2, 1],
    ["Mateo Quiroga", "MID", 23, 10, 721, 1, 3],
    ["Ivan Petrov", "FWD", 25, 10, 802, 7, 2],
    ["Leo Carver", "MID", 18, 3, 64, 0, 0],
  ],
  brighton: [
    ["Jakub Nowak", "GK", 24, 9, 810, 0, 0],
    ["Theo Lambert", "DEF", 21, 10, 884, 0, 3],
    ["Kaito Mori", "MID", 25, 11, 930, 4, 3],
    ["Felix Brandt", "FWD", 22, 9, 615, 3, 2],
    ["Ruben Ortega", "DEF", 27, 7, 540, 1, 0],
  ],
  chelsea: [
    ["Simon Lacroix", "GK", 28, 11, 990, 0, 0],
    ["Marcus Hale", "DEF", 22, 11, 920, 1, 1],
    ["Andre Costa", "MID", 20, 10, 845, 2, 6],
    ["Tobi Adeyemi", "FWD", 23, 10, 760, 6, 3],
    ["Kieran Walsh", "MID", 26, 7, 402, 0, 1],
  ],
  "coventry-city": [
    ["Dan Fletcher", "GK", 30, 11, 990, 0, 0],
    ["Joel Hartley", "DEF", 26, 11, 955, 1, 1],
    ["Ollie Brennan", "MID", 24, 10, 870, 2, 3],
    ["Ade Bankole", "FWD", 22, 10, 688, 4, 1],
    ["Matt Sinclair", "DEF", 32, 4, 271, 0, 0],
  ],
  "crystal-palace": [
    ["Lewis Graham", "GK", 33, 11, 990, 0, 0],
    ["Isaac Boateng", "DEF", 24, 11, 910, 0, 1],
    ["Pablo Medina", "MID", 27, 10, 835, 2, 4],
    ["Jordan Clarke", "FWD", 21, 9, 590, 3, 0],
    ["Ethan Moss", "MID", 19, 5, 205, 0, 1],
  ],
  everton: [
    ["Ryan Doherty", "GK", 29, 11, 990, 0, 0],
    ["Connor Byrne", "DEF", 27, 11, 960, 1, 0],
    ["Malik Diallo", "MID", 25, 10, 822, 1, 3],
    ["Scott Henley", "FWD", 30, 9, 640, 4, 1],
    ["Alfie Turner", "DEF", 20, 6, 380, 0, 0],
  ],
  fulham: [
    ["Bruno Tavares", "GK", 32, 11, 990, 0, 0],
    ["Will Hastings", "DEF", 29, 10, 890, 0, 2],
    ["Emre Kaya", "MID", 26, 10, 801, 3, 3],
    ["Rafael Lima", "FWD", 24, 10, 712, 5, 2],
    ["George Fenwick", "MID", 22, 7, 455, 1, 0],
  ],
  "hull-city": [
    ["Karl Lindqvist", "GK", 27, 11, 990, 0, 0],
    ["Tom Ridley", "DEF", 25, 11, 940, 1, 0],
    ["Nathan Cole", "MID", 23, 10, 856, 2, 2],
    ["Sami Haddad", "FWD", 26, 10, 730, 4, 1],
    ["Jack Hollis", "DEF", 21, 4, 260, 0, 0],
  ],
  "ipswich-town": [
    ["Alex Morton", "GK", 28, 11, 990, 0, 0],
    ["Luke Pearson", "DEF", 24, 11, 905, 0, 1],
    ["Hugo Martel", "MID", 22, 10, 838, 1, 3],
    ["Chris Ogun", "FWD", 25, 10, 674, 3, 2],
    ["Ben Kerr", "MID", 30, 6, 330, 0, 0],
  ],
  "leeds-united": [
    ["Mats Eriksen", "GK", 26, 11, 990, 0, 0],
    ["Joe Barker", "DEF", 23, 11, 928, 1, 1],
    ["Daniel Rocha", "MID", 27, 10, 861, 2, 4],
    ["Kyle Nolan", "FWD", 24, 10, 702, 5, 0],
    ["Finn Ashby", "DEF", 19, 3, 148, 0, 0],
  ],
  liverpool: [
    ["Paulo Ventura", "GK", 30, 11, 990, 0, 0],
    ["Aaron Whitby", "DEF", 26, 11, 950, 1, 4],
    ["Lucas Fontaine", "MID", 24, 10, 880, 4, 5],
    ["Samuel Eze", "FWD", 23, 10, 795, 8, 3],
    ["Max Reilly", "MID", 20, 6, 360, 1, 0],
  ],
  "manchester-city": [
    ["Henrik Dahl", "GK", 31, 10, 900, 0, 0],
    ["Adrian Silva", "DEF", 27, 11, 990, 2, 1],
    ["Joon Park", "MID", 25, 11, 910, 3, 6],
    ["Matias Herrera", "FWD", 24, 10, 820, 9, 2],
    ["Reece Cooper", "DEF", 21, 6, 450, 0, 1],
  ],
  "manchester-united": [
    ["Oscar Lund", "GK", 25, 11, 990, 0, 0],
    ["Darnell Price", "DEF", 22, 11, 930, 0, 2],
    ["Enzo Moretti", "MID", 26, 10, 850, 3, 3],
    ["Kwame Asante", "FWD", 21, 10, 690, 4, 2],
    ["Liam Doyle", "MID", 28, 8, 505, 1, 1],
  ],
  "newcastle-united": [
    ["Craig Robson", "GK", 32, 11, 990, 0, 0],
    ["Victor Lindgren", "DEF", 26, 11, 945, 2, 0],
    ["Jonah Wright", "MID", 23, 10, 880, 2, 4],
    ["Abdou Sarr", "FWD", 25, 10, 760, 6, 1],
    ["Harry Bell", "DEF", 20, 5, 290, 0, 0],
  ],
  "nottingham-forest": [
    ["Nikola Jovic", "GK", 28, 11, 990, 0, 0],
    ["Sean Ward", "DEF", 27, 11, 915, 1, 1],
    ["Thiago Reis", "MID", 24, 10, 845, 2, 3],
    ["Marcus Lowe", "FWD", 26, 10, 710, 5, 1],
    ["Josh Keane", "MID", 21, 6, 340, 0, 1],
  ],
  sunderland: [
    ["Lars Vik", "GK", 25, 11, 990, 0, 0],
    ["Michael Dunn", "DEF", 24, 11, 935, 0, 1],
    ["Ibrahim Toure", "MID", 22, 10, 860, 3, 2],
    ["Jamie Forsyth", "FWD", 20, 10, 655, 4, 2],
    ["Cole Ramsey", "DEF", 29, 6, 420, 1, 0],
  ],
  "tottenham-hotspur": [
    ["Gabriel Nunes", "GK", 29, 11, 990, 0, 0],
    ["Archie Bennett", "DEF", 23, 11, 925, 1, 2],
    ["Min-jae Seo", "MID", 26, 10, 870, 3, 4],
    ["Ethan Brooks", "FWD", 22, 10, 745, 5, 3],
    ["Rhys Morgan", "MID", 19, 4, 180, 0, 0],
  ],
};

export function getClubs(): Club[] {
  return CLUBS;
}

export function getClub(slug: string): Club | undefined {
  return CLUBS.find((club) => club.slug === slug);
}

export function getSquad(slug: string): Player[] {
  return (SQUADS[slug] ?? []).map(
    ([name, position, age, appearances, minutes, goals, assists], i) => ({
      id: `${slug}-${i}`,
      name,
      position,
      age,
      appearances,
      minutes,
      goals,
      assists,
    }),
  );
}

/** Per-club figures for the picker. Every value is computed from getSquad rows. */
export function getClubSummaries(): ClubSummary[] {
  return CLUBS.map((club) => {
    const squad = getSquad(club.slug);
    const averageAge = squad.length
      ? squad.reduce((sum, p) => sum + p.age, 0) / squad.length
      : null;
    const top = squad.reduce<Player | null>(
      (best, p) =>
        !best || p.goals > best.goals || (p.goals === best.goals && p.assists > best.assists)
          ? p
          : best,
      null,
    );
    return {
      ...club,
      squadSize: squad.length,
      averageAge,
      topScorer: top && top.goals > 0 ? { name: top.name, goals: top.goals } : null,
    };
  });
}
