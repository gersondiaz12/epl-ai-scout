"""Load the current season from the Fantasy Premier League API.

    uv run python -m app.ingest.fpl            # fetch (cached per day) and load
    uv run python -m app.ingest.fpl --refresh  # ignore today's cache

Raw responses are cached under data/raw/fpl/<date>/ (gitignored), so a rerun on
the same day doesn't hit FPL again and a load can be traced to its inputs.
Stats rows for the season are replaced in one transaction, and the load is
rolled back unless every player's summed rows match FPL's season totals.
"""

import argparse
import json
import logging
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.ingest.club_reference import CLUB_REFERENCE, PROMOTED
from app.metrics import Totals, sum_totals
from app.models import (
    Club,
    ClubSeason,
    ClubSourceId,
    Player,
    PlayerSeasonStats,
    PlayerSourceId,
    Position,
    Season,
)

log = logging.getLogger("ingest.fpl")

SOURCE = "fpl"
BASE_URL = "https://fantasy.premierleague.com/api"
CACHE_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "fpl"
POSITIONS = {1: Position.GK, 2: Position.DEF, 3: Position.MID, 4: Position.FWD}

Json = dict[str, Any]


class ReconciliationError(Exception):
    pass


# ---------- Fetching ----------


class FplClient:
    """GETs FPL endpoints with retries, caching each response as JSON."""

    def __init__(self, cache_dir: Path, refresh: bool = False) -> None:
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.http = httpx.Client(
            base_url=BASE_URL,
            timeout=20,
            headers={"User-Agent": "epl-ai-scout-ingest/0.1"},
        )

    def get(self, path: str) -> Any:
        cache_file = self.cache_dir / (path.strip("/").replace("/", "__") + ".json")
        if cache_file.exists() and not self.refresh:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        for attempt in range(4):
            try:
                response = self.http.get(path)
                response.raise_for_status()
                break
            except httpx.HTTPError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
        data = response.json()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        return data


# ---------- Pure transforms (unit-tested) ----------


def season_label(first_deadline: date) -> str:
    """A season starting in August 2026 is '2026-27'."""
    return f"{first_deadline.year}-{(first_deadline.year + 1) % 100:02d}"


def history_totals(history: list[Json], fixtures: dict[int, Json]) -> dict[int, Totals]:
    """Sum a player's match history per FPL team id (the club they played for).

    The player's club in a match is the fixture side that isn't the opponent,
    so a mid-season transfer splits naturally into one entry per club.
    Appearances count matches with any minutes.
    """
    by_team: dict[int, Totals] = defaultdict(Totals)
    for match in history:
        fixture = fixtures[match["fixture"]]
        team = fixture["team_h"] if match["was_home"] else fixture["team_a"]
        by_team[team] = by_team[team] + Totals(
            appearances=1 if match["minutes"] > 0 else 0,
            minutes=match["minutes"],
            goals=match["goals_scored"],
            assists=match["assists"],
            xg=Decimal(match["expected_goals"]),
            xa=Decimal(match["expected_assists"]),
            xg_conceded=Decimal(match["expected_goals_conceded"]),
            saves=match["saves"],
        )
    return dict(by_team)


@dataclass(frozen=True)
class StatsRow:
    element_code: int
    team_code: int
    position: Position
    is_current_club: bool
    totals: Totals


def stats_rows(
    element: Json, by_team: dict[int, Totals], team_codes: dict[int, int]
) -> list[StatsRow]:
    """One row per club the player appeared for, plus a row for their current
    club even with no appearances (so they appear in its squad).

    FPL history also lists matches at a former club where the player didn't
    get on; those carry no stats and would only add empty "left" rows.
    """
    current_team = element["team"]
    totals_by_team = {
        team: totals
        for team, totals in by_team.items()
        if team == current_team or totals.appearances > 0
    }
    totals_by_team.setdefault(current_team, Totals())
    position = POSITIONS[element["element_type"]]
    return [
        StatsRow(
            element_code=element["code"],
            team_code=team_codes[team],
            position=position,
            is_current_club=team == current_team,
            totals=totals,
        )
        for team, totals in sorted(totals_by_team.items())
    ]


def reconcile(element: Json, rows: list[StatsRow]) -> list[str]:
    """Differences between the summed rows and FPL's own season totals."""
    total = sum_totals(r.totals for r in rows)
    expected = {
        "minutes": (total.minutes, element["minutes"]),
        "goals": (total.goals, element["goals_scored"]),
        "assists": (total.assists, element["assists"]),
        "xg": (total.xg, Decimal(element["expected_goals"])),
        "xa": (total.xa, Decimal(element["expected_assists"])),
        "saves": (total.saves, element["saves"]),
    }
    return [
        f"{element['web_name']} ({element['code']}) {name}: rows {got} != fpl {want}"
        for name, (got, want) in expected.items()
        if got != want
    ]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def player_name(element: Json) -> str:
    """The name people know the player by. FPL sets known_name when it differs
    from the legal name (e.g. 'Evanilson' for Francisco Evanilson de Lima Barbosa).
    """
    known = (element.get("known_name") or "").strip()
    return known or f"{element['first_name']} {element['second_name']}".strip()


# ---------- Loading ----------


def fetch(client: FplClient, workers: int = 5) -> tuple[Json, list[Json], dict[int, list[Json]]]:
    bootstrap = client.get("/bootstrap-static/")
    fixtures = client.get("/fixtures/")
    played = [e for e in bootstrap["elements"] if e["minutes"] > 0]
    log.info("fetching match history for %d players who have played", len(played))

    def history(element: Json) -> tuple[int, list[Json]]:
        return element["id"], client.get(f"/element-summary/{element['id']}/")["history"]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        histories = dict(pool.map(history, played))
    return bootstrap, fixtures, histories


def load(
    session: Session, bootstrap: Json, fixtures: list[Json], histories: dict[int, list[Json]]
) -> dict[str, int]:
    deadlines = [datetime.fromisoformat(e["deadline_time"]).date() for e in bootstrap["events"]]
    label = season_label(min(deadlines))

    # Season: upsert, and make it the only current one.
    season = session.scalar(select(Season).where(Season.label == label))
    if season is None:
        season = Season(label=label, start_date=min(deadlines), end_date=max(deadlines))
        session.add(season)
    season.start_date, season.end_date = min(deadlines), max(deadlines)
    session.execute(update(Season).where(Season.label != label).values(is_current=False))
    season.is_current = True
    session.flush()

    # Clubs, keyed by FPL's stable team code.
    club_by_code: dict[int, Club] = {
        int(sid.external_id): sid.club
        for sid in session.scalars(select(ClubSourceId).where(ClubSourceId.source == SOURCE))
    }
    team_codes = {t["id"]: t["code"] for t in bootstrap["teams"]}
    session.execute(delete(ClubSeason).where(ClubSeason.season_id == season.id))
    for team in bootstrap["teams"]:
        ref = CLUB_REFERENCE.get(team["code"])
        club = club_by_code.get(team["code"])
        if club is None:
            club = Club(slug=ref.slug if ref else slugify(team["name"]))
            club.source_ids.append(ClubSourceId(source=SOURCE, external_id=str(team["code"])))
            session.add(club)
            club_by_code[team["code"]] = club
        club.name = ref.name if ref else team["name"]
        club.short_name = team["short_name"]
        club.ground, club.city = (ref.ground, ref.city) if ref else (None, None)
        session.flush()
        session.add(
            ClubSeason(
                club_id=club.id,
                season_id=season.id,
                promoted=team["code"] in PROMOTED.get(label, set()),
            )
        )

    # Players, keyed by FPL's stable element code.
    player_by_code: dict[int, Player] = {
        int(sid.external_id): sid.player
        for sid in session.scalars(select(PlayerSourceId).where(PlayerSourceId.source == SOURCE))
    }
    for e in bootstrap["elements"]:
        player = player_by_code.get(e["code"])
        if player is None:
            player = Player()
            player.source_ids.append(PlayerSourceId(source=SOURCE, external_id=str(e["code"])))
            session.add(player)
            player_by_code[e["code"]] = player
        player.name = player_name(e)
        player.display_name = e["web_name"]
        player.birth_date = date.fromisoformat(e["birth_date"]) if e.get("birth_date") else None
    session.flush()

    # Stats: replace this season's rows from this source.
    fixtures_by_id = {f["id"]: f for f in fixtures}
    session.execute(
        delete(PlayerSeasonStats).where(
            PlayerSeasonStats.season_id == season.id, PlayerSeasonStats.source == SOURCE
        )
    )
    problems: list[str] = []
    row_count = 0
    for e in bootstrap["elements"]:
        by_team = history_totals(histories.get(e["id"], []), fixtures_by_id)
        rows = stats_rows(e, by_team, team_codes)
        problems += reconcile(e, rows)
        for r in rows:
            t = r.totals
            session.add(
                PlayerSeasonStats(
                    player_id=player_by_code[r.element_code].id,
                    season_id=season.id,
                    club_id=club_by_code[r.team_code].id,
                    position=r.position,
                    is_current_club=r.is_current_club,
                    appearances=t.appearances,
                    minutes=t.minutes,
                    goals=t.goals,
                    assists=t.assists,
                    xg=t.xg,
                    xa=t.xa,
                    xg_conceded=t.xg_conceded,
                    saves=t.saves,
                    source=SOURCE,
                )
            )
            row_count += 1
    if problems:
        raise ReconciliationError(
            f"{len(problems)} mismatches against FPL totals, e.g.:\n" + "\n".join(problems[:10])
        )
    session.flush()
    return {
        "clubs": len(bootstrap["teams"]),
        "players": len(bootstrap["elements"]),
        "stats_rows": row_count,
        "players_with_two_clubs": row_count - len(bootstrap["elements"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="ignore today's cached responses")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    client = FplClient(CACHE_ROOT / date.today().isoformat(), refresh=args.refresh)
    bootstrap, fixtures, histories = fetch(client)
    with SessionLocal() as session, session.begin():
        summary = load(session, bootstrap, fixtures, histories)
    log.info("loaded: %s", summary)


if __name__ == "__main__":
    main()
