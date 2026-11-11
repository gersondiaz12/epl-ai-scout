/**
 * TEMPORARY SAMPLE DATA. Delete this file once apps/api serves real data,
 * then point the imports of getClubs/getClub/getSquad at the API client.
 *
 * Clubs are the real 2026–27 Premier League line-up. Every player, age and
 * minute figure below is FICTIONAL and must never be presented as real.
 */
import type { Club, Player, Position } from "./types";

export const IS_SAMPLE_DATA = true;

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

/** Fictional players: [name, position, age, league minutes]. */
type Row = [string, Position, number, number];

const SQUADS: Record<string, Row[]> = {
  arsenal: [["Tomas Varga", "GK", 27, 990], ["Elliot Marsh", "DEF", 24, 945], ["Kofi Mensah", "MID", 22, 812], ["Rui Saldanha", "FWD", 26, 703], ["Owen Pryce", "DEF", 30, 410]],
  "aston-villa": [["Marek Dvorak", "GK", 31, 990], ["Jamal Okafor", "DEF", 25, 900], ["Luca Benedetti", "MID", 28, 866], ["Sam Whitlock", "FWD", 21, 534], ["Harvey Lane", "MID", 19, 122]],
  bournemouth: [["Pieter Smit", "GK", 29, 990], ["Callum Reid", "DEF", 23, 871], ["Yassine Amrani", "MID", 24, 790], ["Diego Ferraz", "FWD", 27, 655], ["Noah Ellison", "DEF", 20, 318]],
  brentford: [["Anders Holm", "GK", 26, 900], ["Ben Ashworth", "DEF", 28, 990], ["Mateo Quiroga", "MID", 23, 721], ["Ivan Petrov", "FWD", 25, 802], ["Leo Carver", "MID", 18, 64]],
  brighton: [["Jakub Nowak", "GK", 24, 810], ["Theo Lambert", "DEF", 21, 884], ["Kaito Mori", "MID", 25, 930], ["Felix Brandt", "FWD", 22, 615], ["Ruben Ortega", "DEF", 27, 540]],
  chelsea: [["Simon Lacroix", "GK", 28, 990], ["Marcus Hale", "DEF", 22, 920], ["Andre Costa", "MID", 20, 845], ["Tobi Adeyemi", "FWD", 23, 760], ["Kieran Walsh", "MID", 26, 402]],
  "coventry-city": [["Dan Fletcher", "GK", 30, 990], ["Joel Hartley", "DEF", 26, 955], ["Ollie Brennan", "MID", 24, 870], ["Ade Bankole", "FWD", 22, 688], ["Matt Sinclair", "DEF", 32, 271]],
  "crystal-palace": [["Lewis Graham", "GK", 33, 990], ["Isaac Boateng", "DEF", 24, 910], ["Pablo Medina", "MID", 27, 835], ["Jordan Clarke", "FWD", 21, 590], ["Ethan Moss", "MID", 19, 205]],
  everton: [["Ryan Doherty", "GK", 29, 990], ["Connor Byrne", "DEF", 27, 960], ["Malik Diallo", "MID", 25, 822], ["Scott Henley", "FWD", 30, 640], ["Alfie Turner", "DEF", 20, 380]],
  fulham: [["Bruno Tavares", "GK", 32, 990], ["Will Hastings", "DEF", 29, 890], ["Emre Kaya", "MID", 26, 801], ["Rafael Lima", "FWD", 24, 712], ["George Fenwick", "MID", 22, 455]],
  "hull-city": [["Karl Lindqvist", "GK", 27, 990], ["Tom Ridley", "DEF", 25, 940], ["Nathan Cole", "MID", 23, 856], ["Sami Haddad", "FWD", 26, 730], ["Jack Hollis", "DEF", 21, 260]],
  "ipswich-town": [["Alex Morton", "GK", 28, 990], ["Luke Pearson", "DEF", 24, 905], ["Hugo Martel", "MID", 22, 838], ["Chris Ogun", "FWD", 25, 674], ["Ben Kerr", "MID", 30, 330]],
  "leeds-united": [["Mats Eriksen", "GK", 26, 990], ["Joe Barker", "DEF", 23, 928], ["Daniel Rocha", "MID", 27, 861], ["Kyle Nolan", "FWD", 24, 702], ["Finn Ashby", "DEF", 19, 148]],
  liverpool: [["Paulo Ventura", "GK", 30, 990], ["Aaron Whitby", "DEF", 26, 950], ["Lucas Fontaine", "MID", 24, 880], ["Samuel Eze", "FWD", 23, 795], ["Max Reilly", "MID", 20, 360]],
  "manchester-city": [["Henrik Dahl", "GK", 31, 900], ["Adrian Silva", "DEF", 27, 990], ["Joon Park", "MID", 25, 910], ["Matias Herrera", "FWD", 24, 820], ["Reece Cooper", "DEF", 21, 450]],
  "manchester-united": [["Oscar Lund", "GK", 25, 990], ["Darnell Price", "DEF", 22, 930], ["Enzo Moretti", "MID", 26, 850], ["Kwame Asante", "FWD", 21, 690], ["Liam Doyle", "MID", 28, 505]],
  "newcastle-united": [["Craig Robson", "GK", 32, 990], ["Victor Lindgren", "DEF", 26, 945], ["Jonah Wright", "MID", 23, 880], ["Abdou Sarr", "FWD", 25, 760], ["Harry Bell", "DEF", 20, 290]],
  "nottingham-forest": [["Nikola Jovic", "GK", 28, 990], ["Sean Ward", "DEF", 27, 915], ["Thiago Reis", "MID", 24, 845], ["Marcus Lowe", "FWD", 26, 710], ["Josh Keane", "MID", 21, 340]],
  sunderland: [["Lars Vik", "GK", 25, 990], ["Michael Dunn", "DEF", 24, 935], ["Ibrahim Toure", "MID", 22, 860], ["Jamie Forsyth", "FWD", 20, 655], ["Cole Ramsey", "DEF", 29, 420]],
  "tottenham-hotspur": [["Gabriel Nunes", "GK", 29, 990], ["Archie Bennett", "DEF", 23, 925], ["Min-jae Seo", "MID", 26, 870], ["Ethan Brooks", "FWD", 22, 745], ["Rhys Morgan", "MID", 19, 180]],
};

export function getClubs(): Club[] {
  return CLUBS;
}

export function getClub(slug: string): Club | undefined {
  return CLUBS.find((club) => club.slug === slug);
}

export function getSquad(slug: string): Player[] {
  return (SQUADS[slug] ?? []).map(([name, position, age, minutes], i) => ({
    id: `${slug}-${i}`,
    name,
    position,
    age,
    minutes,
  }));
}
