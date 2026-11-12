from collections import defaultdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.metrics import (
    METRICS,
    METRICS_BY_POSITION,
    PER90_MIN_MINUTES,
    Totals,
    per90,
    per90_values,
    percentile,
    sum_totals,
)
from app.models import PlayerSeasonStats, Position
from app.queries import age_on, get_season, row_totals, season_rows
from app.schemas import (
    ClubRef,
    ClubSeasonTotals,
    Per90,
    PercentileRow,
    Percentiles,
    PlayerOut,
    SeasonTotals,
)

router = APIRouter(prefix="/players", tags=["players"])

SessionDep = Annotated[Session, Depends(get_session)]
SeasonQuery = Annotated[
    str | None, Query(description="Season label, e.g. 2026-27. Default: current.")
]


def club_ref(row: PlayerSeasonStats) -> ClubRef:
    return ClubRef(
        slug=row.club.slug, name=row.club.name, short_name=row.club.short_name, city=row.club.city
    )


def current_row(rows: list[PlayerSeasonStats]) -> PlayerSeasonStats:
    return next((r for r in rows if r.is_current_club), rows[0])


def build_percentiles(position: Position, totals: Totals, pool: list[Totals]) -> Percentiles:
    """Rank the player's per-90 rates against same-position players with enough minutes."""
    eligible = [t for t in pool if t.minutes >= PER90_MIN_MINUTES]
    if totals.minutes < PER90_MIN_MINUTES or not eligible:
        return Percentiles(pool_size=len(eligible), min_minutes=PER90_MIN_MINUTES, rows=None)
    rows = []
    for key in METRICS_BY_POSITION[position]:
        metric = METRICS[key]
        value = per90(metric.total(totals), totals.minutes)
        pool_values = [per90(metric.total(t), t.minutes) for t in eligible]
        rows.append(
            PercentileRow(
                key=key,
                label=metric.label,
                per90=value,
                percentile=percentile(value, pool_values, metric.higher_is_better),
                higher_is_better=metric.higher_is_better,
            )
        )
    return Percentiles(pool_size=len(eligible), min_minutes=PER90_MIN_MINUTES, rows=rows)


@router.get("/{player_id}")
def get_player(player_id: int, session: SessionDep, season: SeasonQuery = None) -> PlayerOut:
    s = get_season(session, season)
    all_rows = season_rows(session, s.id)

    by_player: dict[int, list[PlayerSeasonStats]] = defaultdict(list)
    for r in all_rows:
        by_player[r.player_id].append(r)
    rows = by_player.get(player_id)
    if not rows:
        raise HTTPException(404, f"Player {player_id} has no league record in {s.label}")

    current = current_row(rows)
    position = current.position
    totals = sum_totals(row_totals(r) for r in rows)
    # Comparison pool: every player whose current position matches, totals across clubs.
    pool = [
        sum_totals(row_totals(r) for r in player_rows)
        for player_rows in by_player.values()
        if current_row(player_rows).position == position
    ]
    player = current.player
    return PlayerOut(
        id=player.id,
        name=player.name,
        display_name=player.display_name,
        birth_date=player.birth_date,
        age=age_on(player.birth_date, date.today()),
        position=position,
        season=s.label,
        club=club_ref(current),
        totals=SeasonTotals(
            appearances=totals.appearances,
            minutes=totals.minutes,
            goals=totals.goals,
            assists=totals.assists,
        ),
        by_club=[
            ClubSeasonTotals(
                club=club_ref(r),
                is_current_club=r.is_current_club,
                appearances=r.appearances,
                minutes=r.minutes,
                goals=r.goals,
                assists=r.assists,
            )
            for r in sorted(rows, key=lambda r: not r.is_current_club)
        ],
        per90=Per90(**per90_values(totals)),
        percentiles=build_percentiles(position, totals, pool),
    )
