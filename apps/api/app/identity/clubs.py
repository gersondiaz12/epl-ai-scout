"""Link a source's clubs to ours (club_source_ids), for club evidence in matching."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Club, ClubSeason, ClubSourceId, Season
from app.text import normalize

NOISE = {"fc", "afc"}
# Our name -> the source's, normalised, where they differ beyond "FC"/"AFC".
CLUB_ALIASES: dict[str, str] = {}


def club_key(name: str) -> str:
    return " ".join(w for w in normalize(name).split() if w not in NOISE)


def club_map(session: Session, source: str) -> dict[str, int]:
    """External club id -> our club id, as stored."""
    return {
        c.external_id: c.club_id
        for c in session.scalars(select(ClubSourceId).where(ClubSourceId.source == source))
    }


def link_clubs(session: Session, source: str, clubs: dict[str, str], *, write: bool = True):
    """Link every club in `clubs` (external id -> name) to one of this season's
    clubs by name. Fails unless all of them resolve, so a club is never guessed."""
    ours = {
        CLUB_ALIASES.get(club_key(c.name), club_key(c.name)): c.id
        for c in session.scalars(
            select(Club)
            .join(ClubSeason, ClubSeason.club_id == Club.id)
            .join(Season, Season.id == ClubSeason.season_id)
            .where(Season.is_current)
        )
    }
    stored = club_map(session, source)
    mapping, missing = {}, []
    for ext, name in sorted(clubs.items()):
        cid = stored.get(ext) or ours.get(club_key(name))
        if cid is None:
            missing.append(f"{ext} {name}")
        else:
            mapping[ext] = cid
    if missing:
        raise RuntimeError(f"{source} clubs with no club of ours: {', '.join(missing)}")
    if write:
        linked_clubs = {cid for cid in stored.values()}
        for ext, cid in mapping.items():
            if ext not in stored and cid not in linked_clubs:
                session.add(ClubSourceId(club_id=cid, source=source, external_id=ext))
                linked_clubs.add(cid)
        session.flush()
    return {**stored, **mapping}
