from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.metrics import PER90_MIN_MINUTES, per90_values, sum_totals
from app.models import PlayerSeasonStats, Position
from app.queries import club_ref, current_row, get_season, row_totals, season_rows
from app.schemas import Per90, PositionOut, PositionPlayerOut

router = APIRouter(prefix="/positions", tags=["players"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/{position}")
def position_players(
    position: Position,
    session: SessionDep,
    season: Annotated[
        str | None, Query(description="Season label, e.g. 2026-27. Default: current.")
    ] = None,
) -> PositionOut:
    """Every league player whose current position is `position`, most minutes first.

    Totals and per-90 rates span all the player's clubs this season; rates are
    null under the minutes threshold. The club is the player's current one.
    """
    s = get_season(session, season)
    by_player: dict[int, list[PlayerSeasonStats]] = defaultdict(list)
    for r in season_rows(session, s.id):
        by_player[r.player_id].append(r)

    players = []
    for rows in by_player.values():
        current = current_row(rows)
        if current.position != position:
            continue
        totals = sum_totals(row_totals(r) for r in rows)
        players.append(
            PositionPlayerOut(
                player_id=current.player_id,
                name=current.player.name,
                club=club_ref(current),
                appearances=totals.appearances,
                minutes=totals.minutes,
                per90=Per90(**per90_values(totals)),
            )
        )
    players.sort(key=lambda p: (-p.minutes, p.name))
    return PositionOut(
        season=s.label, position=position, min_minutes=PER90_MIN_MINUTES, players=players
    )
