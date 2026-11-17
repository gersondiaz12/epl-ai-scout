from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.metrics import PER90_MIN_MINUTES, per90_values, sum_totals
from app.models import PlayerSeasonStats
from app.queries import club_ref, current_row, get_season, row_totals, season_rows
from app.schemas import InFormOut, InFormPlayerOut, Per90

router = APIRouter(prefix="/in-form", tags=["players"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("")
def in_form(
    session: SessionDep,
    season: Annotated[
        str | None, Query(description="Season label, e.g. 2026-27. Default: current.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="How many players to return.")] = 50,
) -> InFormOut:
    """League players ranked by FPL form, highest first; season minutes break ties.

    Only players with at least the per-90 minutes threshold this season are
    ranked, so a single good cameo can't top the list.
    """
    s = get_season(session, season)
    by_player: dict[int, list[PlayerSeasonStats]] = defaultdict(list)
    for r in season_rows(session, s.id):
        by_player[r.player_id].append(r)

    eligible = []
    without_form = 0
    for rows in by_player.values():
        totals = sum_totals(row_totals(r) for r in rows)
        if totals.minutes < PER90_MIN_MINUTES:
            continue
        current = current_row(rows)
        if current.form is None:
            without_form += 1
            continue
        eligible.append((current, totals))
    eligible.sort(key=lambda e: (-e[0].form, -e[1].minutes, e[0].player.name))

    players = []
    rank = 0
    for i, (row, totals) in enumerate(eligible):
        if i == 0 or row.form != eligible[i - 1][0].form:
            rank = i + 1
        if i >= limit:
            break
        players.append(
            InFormPlayerOut(
                rank=rank,
                player_id=row.player_id,
                name=row.player.name,
                position=row.position,
                club=club_ref(row),
                form=row.form,
                appearances=totals.appearances,
                minutes=totals.minutes,
                goals=totals.goals,
                assists=totals.assists,
                per90=Per90(**per90_values(totals)),
            )
        )
    return InFormOut(
        season=s.label,
        min_minutes=PER90_MIN_MINUTES,
        pool_size=len(eligible),
        without_form=without_form,
        form_updated_at=max((row.ingested_at for row, _ in eligible), default=None),
        players=players,
    )
