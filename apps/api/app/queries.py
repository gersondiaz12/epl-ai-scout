"""Shared reads used by the routers."""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.metrics import Totals
from app.models import PlayerSeasonStats, Season


def get_season(session: Session, label: str | None) -> Season:
    """The requested season, or the current one. 404 if it doesn't exist."""
    query = select(Season).where(Season.label == label if label else Season.is_current)
    season = session.scalar(query)
    if season is None:
        raise HTTPException(404, f"Season {label!r} not found" if label else "No current season")
    return season


def season_rows(session: Session, season_id: int) -> list[PlayerSeasonStats]:
    """Every stats row in a season, with its player and club loaded."""
    return list(
        session.scalars(
            select(PlayerSeasonStats)
            .where(PlayerSeasonStats.season_id == season_id)
            .options(joinedload(PlayerSeasonStats.player), joinedload(PlayerSeasonStats.club))
        )
    )


def row_totals(row: PlayerSeasonStats) -> Totals:
    return Totals(
        appearances=row.appearances,
        minutes=row.minutes,
        goals=row.goals,
        assists=row.assists,
        xg=row.xg,
        xa=row.xa,
        xg_conceded=row.xg_conceded,
        saves=row.saves,
    )


def age_on(birth_date: date | None, on: date) -> int | None:
    if birth_date is None:
        return None
    return on.year - birth_date.year - ((on.month, on.day) < (birth_date.month, birth_date.day))
