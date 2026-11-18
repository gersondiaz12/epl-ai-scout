"""Football tables owned by apps/api. apps/web keeps its own tables elsewhere.

Per-90 rates and percentiles are not stored: they are computed from the
totals and minutes below (see app/metrics.py), so a rate can never disagree
with the totals it came from.
"""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Stable constraint names so Alembic migrations are deterministic.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class Position(enum.StrEnum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(7), unique=True)  # "2026-27"
    # Null for past seasons loaded from FPL's history, which gives only the
    # label ("2024/25"); dates are never guessed.
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    __table_args__ = (
        # At most one current season.
        Index(
            "uq_seasons_one_current",
            "is_current",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str] = mapped_column(String(3))
    ground: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))

    source_ids: Mapped[list["ClubSourceId"]] = relationship(
        back_populates="club", cascade="all, delete-orphan"
    )


class ClubSeason(Base):
    """Which clubs are in the league in a season."""

    __tablename__ = "club_seasons"

    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), primary_key=True
    )
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True
    )
    promoted: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    club: Mapped[Club] = relationship()
    season: Mapped[Season] = relationship()


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))  # known name, else first + second
    display_name: Mapped[str] = mapped_column(String(100))  # FPL web_name
    birth_date: Mapped[date | None] = mapped_column(Date)

    source_ids: Mapped[list["PlayerSourceId"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    season_stats: Mapped[list["PlayerSeasonStats"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )


class ClubSourceId(Base):
    """An external id for a club, e.g. ('fpl', '3') for Arsenal's stable FPL team code."""

    __tablename__ = "club_source_ids"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(64))

    club: Mapped[Club] = relationship(back_populates="source_ids")

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_club_source_ids_source_external_id"),
        UniqueConstraint("club_id", "source", name="uq_club_source_ids_club_id_source"),
    )


class PlayerSourceId(Base):
    """An external id for a player, e.g. ('fpl', '223340'): FPL's stable element code."""

    __tablename__ = "player_source_ids"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(64))

    player: Mapped[Player] = relationship(back_populates="source_ids")

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_player_source_ids_source_external_id"),
        UniqueConstraint("player_id", "source", name="uq_player_source_ids_player_id_source"),
    )


# Nullable counts pass while null (SQL treats the check as unknown, not false).
DEFENSIVE_NON_NEGATIVE = (
    "starts >= 0 AND tackles >= 0 AND cbi >= 0 AND recoveries >= 0 "
    "AND goals_conceded >= 0 AND clean_sheets >= 0 AND penalties_saved >= 0"
)


class PlayerSeasonStats(Base):
    """League totals for one player at one club in one season.

    A mid-season transfer gives the player two rows in that season, one per club.
    """

    __tablename__ = "player_season_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"))
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"))
    position: Mapped[Position] = mapped_column(
        Enum(Position, name="player_position", values_callable=lambda e: [m.value for m in e])
    )
    # True for the row at the club the source lists the player at today.
    is_current_club: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    appearances: Mapped[int] = mapped_column(Integer)
    minutes: Mapped[int] = mapped_column(Integer)
    goals: Mapped[int] = mapped_column(Integer)
    assists: Mapped[int] = mapped_column(Integer)
    xg: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    xa: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    xg_conceded: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    saves: Mapped[int] = mapped_column(Integer)
    # Defensive and goalkeeping counts. Nullable: rows loaded before these were
    # added stay null until the next ingest fills them.
    starts: Mapped[int | None] = mapped_column(Integer)
    tackles: Mapped[int | None] = mapped_column(Integer)
    cbi: Mapped[int | None] = mapped_column(Integer)  # clearances + blocks + interceptions
    recoveries: Mapped[int | None] = mapped_column(Integer)
    goals_conceded: Mapped[int | None] = mapped_column(Integer)  # while on the pitch
    clean_sheets: Mapped[int | None] = mapped_column(Integer)
    penalties_saved: Mapped[int | None] = mapped_column(Integer)
    # FPL's form: average FPL points per match over the last 30 days, as of
    # ingested_at. A snapshot, not a total, and it belongs to the player, so it
    # is set on the current-club row only (null on former-club rows). Can be
    # negative.
    form: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    source: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped[Player] = relationship(back_populates="season_stats")
    club: Mapped[Club] = relationship()
    season: Mapped[Season] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "season_id",
            "club_id",
            name="uq_player_season_stats_player_season_club",
        ),
        Index("ix_player_season_stats_season_club", "season_id", "club_id"),
        CheckConstraint(
            "appearances >= 0 AND minutes >= 0 AND goals >= 0 AND assists >= 0 "
            "AND saves >= 0 AND xg >= 0 AND xa >= 0 AND xg_conceded >= 0",
            name="non_negative",
        ),
        CheckConstraint(DEFENSIVE_NON_NEGATIVE, name="defensive_non_negative"),
        CheckConstraint("minutes <= appearances * 120", name="minutes_fit_appearances"),
    )


class PlayerSeasonTotals(Base):
    """A player's season totals as a source reports them, with no club split.

    For past seasons, where the source gives one total per player and season
    (FPL's history) rather than match-level data. A field the source didn't
    track that season is null, never 0. The current season lives in
    player_season_stats, split by club.
    """

    __tablename__ = "player_season_totals"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32))

    minutes: Mapped[int] = mapped_column(Integer)
    starts: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    xg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    xa: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    xg_conceded: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    saves: Mapped[int | None] = mapped_column(Integer)
    tackles: Mapped[int | None] = mapped_column(Integer)
    cbi: Mapped[int | None] = mapped_column(Integer)
    recoveries: Mapped[int | None] = mapped_column(Integer)
    goals_conceded: Mapped[int | None] = mapped_column(Integer)
    clean_sheets: Mapped[int | None] = mapped_column(Integer)
    penalties_saved: Mapped[int | None] = mapped_column(Integer)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped[Player] = relationship()
    season: Mapped[Season] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "player_id", "season_id", "source", name="uq_player_season_totals_player_season_source"
        ),
        Index("ix_player_season_totals_season", "season_id"),
        CheckConstraint(
            "minutes >= 0 AND goals >= 0 AND assists >= 0 AND saves >= 0 "
            "AND xg >= 0 AND xa >= 0 AND xg_conceded >= 0 AND " + DEFENSIVE_NON_NEGATIVE,
            name="non_negative",
        ),
    )


class SourceSnapshot(Base):
    """One downloaded version of a bulk dataset, so every row loaded from it
    can be traced to the exact files used.

    `version` is the SHA-256 of the sorted per-file SHA-256s, so the same files
    always give the same version.
    """

    __tablename__ = "source_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))  # "transfermarkt"
    dataset: Mapped[str] = mapped_column(String(128))  # "dcaribou/transfermarkt-datasets"
    version: Mapped[str] = mapped_column(String(64))
    files: Mapped[dict] = mapped_column(JSONB)  # {file: {sha256, etag, last_modified, url}}
    upstream_commit: Mapped[str | None] = mapped_column(String(40))
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Latest dated record in the files (e.g. the last valuation): how current the data is.
    data_through: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("source", "version", name="uq_source_snapshots_source_version"),
    )


class PlayerMarketValue(Base):
    """A market value the source published for a player on a date (EUR, as given).

    Club and league are the source's own labels at that date (the player may
    have been outside the Premier League), not links to our clubs.
    """

    __tablename__ = "player_market_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32))
    valued_on: Mapped[date] = mapped_column(Date)
    value_eur: Mapped[int] = mapped_column(BigInteger)
    club_name: Mapped[str | None] = mapped_column(String(128))
    competition_id: Mapped[str | None] = mapped_column(String(16))  # e.g. "GB1"
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("source_snapshots.id"))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped[Player] = relationship()
    snapshot: Mapped[SourceSnapshot] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "player_id", "source", "valued_on", name="uq_player_market_values_player_source_date"
        ),
        CheckConstraint("value_eur >= 0", name="non_negative"),
    )


class PlayerContract(Base):
    """When the player's contract expires, as the source reported it in a snapshot."""

    __tablename__ = "player_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32))
    expires_on: Mapped[date] = mapped_column(Date)
    club_name: Mapped[str | None] = mapped_column(String(128))  # the source's club at that time
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("source_snapshots.id"))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped[Player] = relationship()
    snapshot: Mapped[SourceSnapshot] = relationship()

    __table_args__ = (
        UniqueConstraint("player_id", "source", name="uq_player_contracts_player_source"),
    )
