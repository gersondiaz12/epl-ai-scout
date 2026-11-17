from collections import defaultdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.metrics import sum_totals
from app.models import PlayerSeasonStats, Position
from app.queries import age_on, club_ref, current_row, get_season, row_totals, season_rows
from app.schemas import PlayerSearchOut, PlayerSearchRow
from app.text import normalize

router = APIRouter(prefix="/players", tags=["players"])

SessionDep = Annotated[Session, Depends(get_session)]
MIN_AGE, MAX_AGE = 15, 45


def match_rank(query: str, names: list[str]) -> int | None:
    """How well a normalised query matches any of a player's normalised names.

    0: the whole name. 1: every query word starts a word of the name.
    2: every query word appears somewhere in the name. None: no match.
    An empty query matches everything equally.
    """
    if not query:
        return 0
    words = query.split()
    best = None
    for name in names:
        name_words = name.split()
        if name == query:
            rank = 0
        elif all(any(w.startswith(q) for w in name_words) for q in words):
            rank = 1
        elif all(q in name for q in words):
            rank = 2
        else:
            continue
        best = rank if best is None else min(best, rank)
    return best


@router.get("")
def search_players(
    session: SessionDep,
    q: Annotated[str, Query(max_length=100, description="Name, accents optional.")] = "",
    position: Position | None = None,
    min_age: Annotated[int | None, Query(ge=MIN_AGE, le=MAX_AGE)] = None,
    max_age: Annotated[int | None, Query(ge=MIN_AGE, le=MAX_AGE)] = None,
    season: Annotated[
        str | None, Query(description="Season label, e.g. 2026-27. Default: current.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> PlayerSearchOut:
    """League players by name, accent-insensitive ("Odegaard" finds "Ødegaard"),
    optionally filtered by current position and age range (inclusive).
    """
    if min_age is not None and max_age is not None and min_age > max_age:
        raise HTTPException(422, "min_age must not be greater than max_age")
    s = get_season(session, season)
    query = normalize(q)
    today = date.today()
    age_filtered = min_age is not None or max_age is not None

    by_player: dict[int, list[PlayerSeasonStats]] = defaultdict(list)
    for r in season_rows(session, s.id):
        by_player[r.player_id].append(r)

    matches = []
    unknown_age_excluded = 0
    for rows in by_player.values():
        current = current_row(rows)
        player = current.player
        if position is not None and current.position != position:
            continue
        rank = match_rank(query, [normalize(player.name), normalize(player.display_name)])
        if rank is None:
            continue
        age = age_on(player.birth_date, today)
        if age_filtered:
            if age is None:
                unknown_age_excluded += 1
                continue
            if (min_age is not None and age < min_age) or (max_age is not None and age > max_age):
                continue
        totals = sum_totals(row_totals(r) for r in rows)
        matches.append(
            (
                rank,
                PlayerSearchRow(
                    player_id=player.id,
                    name=player.name,
                    position=current.position,
                    age=age,
                    club=club_ref(current),
                    appearances=totals.appearances,
                    minutes=totals.minutes,
                    goals=totals.goals,
                    assists=totals.assists,
                ),
            )
        )
    matches.sort(key=lambda m: (m[0], -m[1].minutes, m[1].name))
    return PlayerSearchOut(
        season=s.label,
        total=len(matches),
        unknown_age_excluded=unknown_age_excluded,
        players=[row for _, row in matches[:limit]],
    )
