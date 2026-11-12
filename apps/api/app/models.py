"""Football tables owned by apps/api. apps/web keeps its own tables elsewhere.

Per-90 rates and percentiles are not stored: they are computed from the
totals and minutes below (see app/metrics.py), so a rate can never disagree
with the totals it came from.
"""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
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
        CheckConstraint("minutes <= appearances * 120", name="minutes_fit_appearances"),
    )
