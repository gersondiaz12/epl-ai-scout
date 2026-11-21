"""Load current Premier League market values from the self-hosted Transfermarkt API.

    uv run python -m app.ingest.transfermarkt_api            # reuse today's cached responses
    uv run python -m app.ingest.transfermarkt_api --refresh  # fetch today's responses again
    uv run python -m app.ingest.transfermarkt_api --all-histories

A scheduled ingestion job only: no router imports this module (a test checks),
so a web request can never reach the Transfermarkt API. Used with
Transfermarkt's written permission (see CLAUDE.md). The API is
felipeall/transfermarkt-api running locally; its address is the
TRANSFERMARKT_API_URL setting and must be a local host.

Steps:
1. Fetch the current season's Premier League clubs, then each club's squad
   (Transfermarkt id, birth date and current value, but not the value's date).
2. For each squad player linked to ours whose current value differs from the
   latest one we hold (or who has none), fetch their dated value history.
   --all-histories fetches every linked player's history.
3. Requests go one at a time, at least --delay seconds apart (default 5). A 429
   or 5xx backs off and retries; if the upstream stays blocked, the run stops
   and nothing is loaded. Every response is saved untouched under
   data/raw/transfermarkt-api/<date>/ before it is parsed; a re-run the same day
   reuses those files instead of requesting them again.
4. Link unlinked players of ours to squad players with the identity matcher
   (app.identity; club evidence from club_source_ids), then upsert the
   histories into player_market_values. Only a changed value rewrites a row,
   and rows the bulk dataset loaded keep their league label.

Every record not loaded is counted by reason and logged.
"""

import argparse
import hashlib
import json
import logging
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.identity.clubs import link_clubs
from app.identity.matcher import resolve
from app.identity.stages import Person
from app.ingest.transfermarkt import (
    BATCH,
    LIVE_DATASET,
    PREMIER_LEAGUE,
    SOURCE,
    parse_date,
    snapshot_version,
)
from app.models import PlayerMarketValue, PlayerSourceId, Season, SourceSnapshot

log = logging.getLogger("ingest.transfermarkt_api")

DATASET = LIVE_DATASET
CACHE_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "transfermarkt-api"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_DELAY = 5.0
MIN_DELAY = 2.0  # never faster than this, whatever is passed
BACKOFF = (30.0, 60.0, 120.0)  # waits after a 429/5xx before giving up
RETRY_STATUSES = {429, 500, 502, 503, 504}


class UpstreamBlocked(RuntimeError):
    """The API (or Transfermarkt behind it) kept refusing: stop the run."""


def check_local(base_url: str) -> str:
    host = urlsplit(base_url).hostname
    if host not in LOCAL_HOSTS:
        raise ValueError(f"TRANSFERMARKT_API_URL must be a local host, got {host!r}")
    return base_url.rstrip("/")


def season_id(label: str) -> str:
    """Our "2026-27" -> Transfermarkt's season id "2026"."""
    return label.split("-", 1)[0]


# ---------- Fetching (throttled, cached untouched) ----------


@dataclass
class Fetcher:
    """One request at a time, at least `delay` seconds apart, every body cached."""

    http: httpx.Client
    folder: Path
    refresh: bool = False
    delay: float = DEFAULT_DELAY
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    requests: int = 0
    reused: int = 0
    _last: float | None = None

    def get(self, path: str, cache_name: str, params: dict | None = None) -> dict | None:
        """The JSON body, from the cache when present. None on 404 (cached as such)."""
        target = self.folder / cache_name
        missing = target.with_suffix(".404")
        if not self.refresh:
            if target.exists():
                self.reused += 1
                return json.loads(target.read_bytes())
            if missing.exists():
                self.reused += 1
                return None
        for wait in (*BACKOFF, None):
            self._throttle()
            try:
                r = self.http.get(path, params=params)
            except httpx.TransportError as exc:
                status, reason = None, repr(exc)
            else:
                status, reason = r.status_code, r.text[:200]
                if status == 200:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    partial = target.with_suffix(".part")
                    partial.write_bytes(r.content)
                    partial.replace(target)
                    missing.unlink(missing_ok=True)
                    return r.json()
                if status == 404:
                    missing.parent.mkdir(parents=True, exist_ok=True)
                    missing.write_text(reason)
                    return None
                if status not in RETRY_STATUSES:
                    raise UpstreamBlocked(f"{path}: HTTP {status}: {reason}")
            if wait is None:
                raise UpstreamBlocked(f"{path}: still failing after retries ({status}: {reason})")
            log.warning("%s: %s, backing off %.0fs", path, status or reason, wait)
            self.sleep(wait)
        raise AssertionError("unreachable")

    def _throttle(self) -> None:
        if self._last is not None:
            remaining = max(self.delay, MIN_DELAY) - (self.clock() - self._last)
            if remaining > 0:
                self.sleep(remaining)
        self._last = self.clock()
        self.requests += 1


@dataclass
class Fetched:
    folder: Path
    season: str
    clubs: dict[str, str]  # Transfermarkt club id -> name
    squads: dict[str, list[dict]]  # club id -> squad entries
    histories: dict[str, dict | None]  # Transfermarkt player id -> body (None: 404)
    stats: dict[str, int] = field(default_factory=dict)


def squad_people(fetched: "Fetched", clubs: dict[str, int]) -> tuple[dict[str, Person], list[str]]:
    """Squad entries for the matcher, once each, with our club for their squad."""
    found: dict[str, Person] = {}
    bad: list[str] = []
    for club_id, entries in fetched.squads.items():
        for e in entries:
            try:
                tid = str(e["id"])
                dob = parse_date(e.get("dateOfBirth"))
            except (KeyError, ValueError) as exc:
                bad.append(f"{club_id}: {exc!r}")
                continue
            ours = clubs.get(club_id)
            prev = found.get(tid)
            found[tid] = Person(
                tid,
                (e.get("name") or tid,),
                dob,
                (prev.club_ids if prev else frozenset()) | ({ours} if ours else set()),
                prev.club_name if prev else fetched.clubs[club_id],
            )
    return found, bad


def match_squads(session: Session, fetched: "Fetched", *, write: bool):
    clubs = link_clubs(session, SOURCE, fetched.clubs, write=write)
    squad, bad = squad_people(fetched, clubs)
    matched = resolve(
        session,
        source=SOURCE,
        dataset=DATASET,
        records=list(squad.values()),
        in_scope=lambda r: True,  # every current Premier League squad player should be ours
    )
    return matched, squad, bad


def latest_values(session: Session) -> dict[str, int]:
    """Transfermarkt id -> the latest value we hold for that player."""
    rows = session.execute(
        select(PlayerSourceId.external_id, PlayerMarketValue.value_eur)
        .join(PlayerMarketValue, PlayerMarketValue.player_id == PlayerSourceId.player_id)
        .where(PlayerSourceId.source == SOURCE, PlayerMarketValue.source == SOURCE)
        .ext(distinct_on(PlayerSourceId.external_id))
        .order_by(PlayerSourceId.external_id, PlayerMarketValue.valued_on.desc())
    )
    return {tid: value for tid, value in rows}


def fetch(
    session: Session,
    *,
    base_url: str,
    cache_root: Path = CACHE_ROOT,
    today: date | None = None,
    refresh: bool = False,
    all_histories: bool = False,
    delay: float = DEFAULT_DELAY,
    transport: httpx.BaseTransport | None = None,  # tests pass a mock, never the live API
    sleep: Callable[[float], None] = time.sleep,
) -> Fetched:
    """Squads, then the histories that may have changed. Reads the DB, writes nothing to it."""
    current = session.scalar(select(Season).where(Season.is_current))
    if current is None:
        raise RuntimeError("no current season: run the FPL ingest first")
    season = season_id(current.label)
    folder = cache_root / (today or date.today()).isoformat()
    with httpx.Client(base_url=check_local(base_url), timeout=120, transport=transport) as http:
        f = Fetcher(http, folder, refresh=refresh, delay=delay, sleep=sleep)
        comp = f.get(
            f"/competitions/{PREMIER_LEAGUE}/clubs",
            f"competition_{PREMIER_LEAGUE}_{season}.json",
            {"season_id": season},
        )
        if comp is None or str(comp.get("seasonId")) != season:
            got = None if comp is None else comp.get("seasonId")
            raise RuntimeError(f"expected {PREMIER_LEAGUE} season {season}, got {got}")
        clubs = {c["id"]: c.get("name") or c["id"] for c in comp["clubs"]}
        squads = {}
        for club_id in clubs:
            body = f.get(
                f"/clubs/{club_id}/players", f"clubs/{club_id}_{season}.json", {"season_id": season}
            )
            squads[club_id] = [] if body is None else body.get("players", [])

        # Linked players, plus squad players the load is about to link: a
        # preview run of the matcher, rolled back (fetch writes nothing).
        held = latest_values(session)
        preview, _, _ = match_squads(
            session, Fetched(folder, season, clubs, squads, {}), write=False
        )
        linked = set(preview.links.values())
        session.rollback()
        histories: dict[str, dict | None] = {}
        unchanged = 0
        for entry in (e for squad in squads.values() for e in squad):
            tid = str(entry["id"])
            if tid in histories:
                continue
            if tid not in linked:
                continue  # not one of ours: no history needed
            if not all_histories and tid in held and held[tid] == entry.get("marketValue"):
                unchanged += 1
                continue
            histories[tid] = f.get(f"/players/{tid}/market_value", f"players/{tid}.json")

    write_manifest(folder, base_url)
    return Fetched(
        folder,
        season,
        clubs,
        squads,
        histories,
        stats={
            "requests": f.requests,
            "reused_from_cache": f.reused,
            "histories_skipped_value_unchanged": unchanged,
        },
    )


def write_manifest(folder: Path, base_url: str) -> dict[str, Any]:
    files = {
        p.relative_to(folder).as_posix(): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(folder.rglob("*.json"))
        if p.name != "manifest.json"
    }
    manifest = {
        "source": SOURCE,
        "dataset": DATASET,
        "base_url": base_url,
        "files": files,
        "version": snapshot_version(files),
        "retrieved_at": datetime.now(UTC).isoformat(),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


# ---------- Loading ----------


def upsert_values(session: Session, rows: list[dict]) -> int:
    """Insert, or rewrite only a changed value. Club and league already held
    (e.g. the bulk dataset's league label, which this API doesn't give) are kept."""
    written = 0
    table = PlayerMarketValue.__table__
    for start in range(0, len(rows), BATCH):
        stmt = pg_insert(PlayerMarketValue).values(rows[start : start + BATCH])
        ex = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            constraint="uq_player_market_values_player_source_date",
            set_={
                "value_eur": ex.value_eur,
                "club_name": func.coalesce(table.c.club_name, ex.club_name),
                "competition_id": func.coalesce(table.c.competition_id, ex.competition_id),
                "snapshot_id": ex.snapshot_id,
                "ingested_at": ex.ingested_at,
            },
            where=table.c.value_eur.is_distinct_from(ex.value_eur),
        )
        written += len(session.execute(stmt.returning(PlayerMarketValue.id)).all())
    return written


def load_live(session: Session, fetched: Fetched) -> dict[str, Any]:
    manifest = json.loads((fetched.folder / "manifest.json").read_text())
    now = datetime.now(UTC)
    current = session.scalar(select(Season).where(Season.is_current))

    matched, squad, bad_squad = match_squads(session, fetched, write=True)
    player_by_tm = {tid: pid for pid, tid in matched.links.items()}

    pl_club_ids = set(fetched.clubs)
    season_start = current.start_date if current else None
    values: list[dict] = []
    skipped: Counter = Counter()
    examples: dict[str, list[str]] = {}

    def skip(reason: str, example: str) -> None:
        skipped[reason] += 1
        examples.setdefault(reason, []).append(example)

    data_through: date | None = None
    for tid, body in fetched.histories.items():
        pid = player_by_tm.get(tid)
        if body is None:
            skip("history_not_found", tid)
            continue
        if pid is None:
            skip("history_for_unlinked_player", tid)
            continue
        for h in body.get("marketValueHistory", []):
            try:
                valued_on = parse_date(h.get("date"))
                value = h.get("marketValue")
                if valued_on is None or value is None:
                    raise ValueError("no date or no value")
                value = int(value)
                if value < 0:
                    raise ValueError("negative value")
            except (TypeError, ValueError) as exc:
                skip("unreadable_valuation", f"{tid} {h.get('date')}: {exc}")
                continue
            data_through = max(data_through or valued_on, valued_on)
            # League only when certain: a current Premier League club, this season.
            in_pl = (
                h.get("clubId") in pl_club_ids
                and season_start is not None
                and valued_on >= season_start
            )
            values.append(
                {
                    "player_id": pid,
                    "source": SOURCE,
                    "valued_on": valued_on,
                    "value_eur": value,
                    "club_name": h.get("clubName") or None,
                    "competition_id": PREMIER_LEAGUE if in_pl else None,
                }
            )

    snapshot = session.scalar(
        select(SourceSnapshot).where(
            SourceSnapshot.source == SOURCE, SourceSnapshot.version == manifest["version"]
        )
    )
    if snapshot is None:
        snapshot = SourceSnapshot(
            source=SOURCE,
            dataset=DATASET,
            version=manifest["version"],
            files=manifest["files"],
            upstream_commit=None,
            built_at=None,
            data_through=data_through,
            retrieved_at=datetime.fromisoformat(manifest["retrieved_at"]),
        )
        session.add(snapshot)
        session.flush()
    matched.run.snapshot_id = snapshot.id
    for v in values:
        v.update(snapshot_id=snapshot.id, ingested_at=now)
    written = upsert_values(session, values) if values else 0

    linked_tm = set(player_by_tm)
    in_squads = set(squad)
    report = {
        "linked_not_in_pl_squads": len(linked_tm - in_squads),
        "squad_players_not_ours": matched.counts["source_records_not_ours"],
    }
    for reason, items in examples.items():
        log.warning("skipped %s: %d, e.g. %s", reason, len(items), "; ".join(items[:5]))
    if bad_squad:
        log.warning("unreadable squad entries: %d, e.g. %s", len(bad_squad), bad_squad[:5])

    return {
        **fetched.stats,
        "snapshot_version": manifest["version"][:12],
        "season": fetched.season,
        "clubs": len(fetched.clubs),
        "squad_players": len(squad),
        "unreadable_squad_entries": len(bad_squad),
        "linked": len(player_by_tm),
        "linked_new": len(matched.new_links),
        "link_methods": matched.counts["new_by_method"],
        "unlinked": matched.counts["unmatched_our_players"],
        **report,
        "histories_fetched": len(fetched.histories),
        "valuations_seen": len(values),
        "valuations_written": written,
        "skipped": dict(skipped),
        "data_through": data_through.isoformat() if data_through else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="fetch today's responses again")
    parser.add_argument(
        "--all-histories", action="store_true", help="fetch every linked player's history"
    )
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="seconds per request")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    with SessionLocal() as session:
        fetched = fetch(
            session,
            base_url=settings.transfermarkt_api_url,
            refresh=args.refresh,
            all_histories=args.all_histories,
            delay=args.delay,
        )
    with SessionLocal() as session, session.begin():
        summary = load_live(session, fetched)
    log.info("loaded: %s", summary)


if __name__ == "__main__":
    main()
