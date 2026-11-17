"""Response models. apps/web mirrors these in apps/web/lib/types.ts."""

from datetime import date, datetime

from pydantic import BaseModel

from app.models import Position


class SeasonOut(BaseModel):
    label: str
    start_date: date
    end_date: date
    per90_min_minutes: int


class TopScorer(BaseModel):
    player_id: int
    name: str
    goals: int


class ClubSummaryOut(BaseModel):
    slug: str
    name: str
    short_name: str
    ground: str | None
    city: str | None
    promoted: bool
    squad_size: int
    average_age: float | None
    top_scorer: TopScorer | None


class Per90(BaseModel):
    """Rates per 90 minutes; null when the player is under the minutes threshold."""

    ga: float | None
    xg: float | None
    xa: float | None
    saves: float | None
    xg_conceded: float | None


class SquadPlayerOut(BaseModel):
    player_id: int
    name: str
    position: Position
    age: int | None
    is_current_club: bool
    appearances: int
    minutes: int
    goals: int
    assists: int
    per90: Per90


class ClubOut(BaseModel):
    slug: str
    name: str
    short_name: str
    ground: str | None
    city: str | None
    promoted: bool
    season: str
    per90_min_minutes: int
    squad: list[SquadPlayerOut]


class ClubRef(BaseModel):
    slug: str
    name: str
    short_name: str
    city: str | None


class ClubSeasonTotals(BaseModel):
    club: ClubRef
    is_current_club: bool
    appearances: int
    minutes: int
    goals: int
    assists: int


class SeasonTotals(BaseModel):
    appearances: int
    minutes: int
    goals: int
    assists: int


class PercentileRow(BaseModel):
    key: str
    label: str
    per90: float
    percentile: float
    higher_is_better: bool


class Percentiles(BaseModel):
    pool_size: int
    min_minutes: int
    rows: list[PercentileRow] | None  # null when the player is under min_minutes


class PlayerOut(BaseModel):
    id: int
    name: str
    display_name: str
    birth_date: date | None
    age: int | None
    position: Position
    season: str
    club: ClubRef
    totals: SeasonTotals
    by_club: list[ClubSeasonTotals]
    per90: Per90
    percentiles: Percentiles


class InFormPlayerOut(BaseModel):
    rank: int  # shared when form is equal; minutes order the tie
    player_id: int
    name: str
    position: Position
    club: ClubRef
    form: float
    appearances: int
    minutes: int
    goals: int
    assists: int
    per90: Per90


class InFormOut(BaseModel):
    season: str
    min_minutes: int
    pool_size: int  # players ranked: at least min_minutes and a form figure
    without_form: int  # players with min_minutes but no form figure, so not ranked
    form_updated_at: datetime | None  # when the ranked players' form was ingested
    players: list[InFormPlayerOut]


class PositionPlayerOut(BaseModel):
    player_id: int
    name: str
    club: ClubRef
    appearances: int
    minutes: int
    per90: Per90  # null rates under min_minutes


class PositionOut(BaseModel):
    season: str
    position: Position
    min_minutes: int
    players: list[PositionPlayerOut]  # most minutes first


class PlayerSearchRow(BaseModel):
    player_id: int
    name: str
    position: Position
    age: int | None
    club: ClubRef  # current club; totals span every club this season
    appearances: int
    minutes: int
    goals: int
    assists: int


class PlayerSearchOut(BaseModel):
    season: str
    total: int  # all matches; `players` holds the first `limit`
    # Left out only because an age filter is set and FPL has no birth date for them.
    unknown_age_excluded: int
    players: list[PlayerSearchRow]  # best match first, then most minutes
