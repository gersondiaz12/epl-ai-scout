from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.metrics import PER90_MIN_MINUTES, per90_values
from app.models import Club, ClubSeason
from app.queries import age_on, get_season, row_totals, season_rows
from app.schemas import ClubOut, ClubSummaryOut, Per90, SquadPlayerOut, TopScorer

router = APIRouter(prefix="/clubs", tags=["clubs"])

SessionDep = Annotated[Session, Depends(get_session)]
SeasonQuery = Annotated[
    str | None, Query(description="Season label, e.g. 2026-27. Default: current.")
]


@router.get("")
def list_clubs(session: SessionDep, season: SeasonQuery = None) -> list[ClubSummaryOut]:
    """Clubs in the season's league, with squad figures computed from player rows."""
    s = get_season(session, season)
    today = date.today()
    memberships = session.scalars(
        select(ClubSeason)
        .where(ClubSeason.season_id == s.id)
        .join(ClubSeason.club)
        .order_by(Club.name)
    ).all()
    rows = season_rows(session, s.id)

    out = []
    for m in memberships:
        club_rows = [r for r in rows if r.club_id == m.club_id]
        current = [r for r in club_rows if r.is_current_club]
        ages = [a for r in current if (a := age_on(r.player.birth_date, today)) is not None]
        top = max(club_rows, key=lambda r: (r.goals, r.assists), default=None)
        out.append(
            ClubSummaryOut(
                slug=m.club.slug,
                name=m.club.name,
                short_name=m.club.short_name,
                ground=m.club.ground,
                city=m.club.city,
                promoted=m.promoted,
                squad_size=len(current),
                average_age=sum(ages) / len(ages) if ages else None,
                top_scorer=TopScorer(player_id=top.player_id, name=top.player.name, goals=top.goals)
                if top and top.goals > 0
                else None,
            )
        )
    return out


@router.get("/{slug}")
def get_club(slug: str, session: SessionDep, season: SeasonQuery = None) -> ClubOut:
    """A club and every player with league minutes for it this season (or in its squad now)."""
    s = get_season(session, season)
    membership = session.scalar(
        select(ClubSeason)
        .join(ClubSeason.club)
        .where(Club.slug == slug, ClubSeason.season_id == s.id)
    )
    if membership is None:
        raise HTTPException(404, f"Club {slug!r} not found in {s.label}")
    today = date.today()
    rows = [r for r in season_rows(session, s.id) if r.club_id == membership.club_id]
    club = membership.club
    return ClubOut(
        slug=club.slug,
        name=club.name,
        short_name=club.short_name,
        ground=club.ground,
        city=club.city,
        promoted=membership.promoted,
        season=s.label,
        per90_min_minutes=PER90_MIN_MINUTES,
        squad=[
            SquadPlayerOut(
                player_id=r.player_id,
                name=r.player.name,
                position=r.position,
                age=age_on(r.player.birth_date, today),
                is_current_club=r.is_current_club,
                appearances=r.appearances,
                minutes=r.minutes,
                goals=r.goals,
                assists=r.assists,
                per90=Per90(**per90_values(row_totals(r))),
            )
            for r in sorted(rows, key=lambda r: (-r.minutes, r.player.name))
        ],
    )
