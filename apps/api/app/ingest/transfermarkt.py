"""Load Transfermarkt market values and contract expiry for our players.

    uv run python -m app.ingest.transfermarkt            # reuse the cached snapshot if unchanged
    uv run python -m app.ingest.transfermarkt --refresh  # download the files again

Source: the dcaribou/transfermarkt-datasets bulk dataset (CC0-1.0), used with
Transfermarkt's written permission (see CLAUDE.md). It is a frozen snapshot:
upstream collection stopped in July 2026, so values end in June 2026 and
contracts reflect that time.

Steps:
1. Download `players` and `player_valuations` (gzipped CSV) into
   data/raw/transfermarkt/<build date>/, untouched, with a manifest of SHA-256s,
   ETags and the upstream commit. The snapshot version is derived from the hashes.
2. Link Transfermarkt players to ours (the Premier League players we hold)
   with the identity matcher (app.identity): manual decisions, stored links,
   rules, then a fuzzy name score. Links, the unmatched queue and the run are
   stored; links are kept on later runs.
3. Upsert each linked player's full valuation history and contract expiry.
   A row is only rewritten when a value differs, so re-running the same
   snapshot changes nothing.

Every record not loaded is counted by reason and logged.
"""

import argparse
import csv
import gzip
import hashlib
import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.identity.clubs import club_map
from app.identity.matcher import resolve
from app.identity.stages import Person
from app.models import PlayerContract, PlayerMarketValue, SourceSnapshot
from app.text import normalize

log = logging.getLogger("ingest.transfermarkt")

SOURCE = "transfermarkt"
DATASET = "dcaribou/transfermarkt-datasets"
LIVE_DATASET = "felipeall/transfermarkt-api"  # app.ingest.transfermarkt_api
BASE_URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/"
COMMIT_URL = f"https://api.github.com/repos/{DATASET}/commits/master"
FILES = ("players", "player_valuations")
CACHE_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "transfermarkt"
PREMIER_LEAGUE = "GB1"
BATCH = 5000  # rows per insert; keeps well under Postgres's 65,535 parameters


# ---------- Download (cached, untouched) ----------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_version(files: dict[str, dict[str, Any]]) -> str:
    """Same files, same version: SHA-256 over the sorted per-file hashes."""
    joined = "\n".join(f"{name}:{files[name]['sha256']}" for name in sorted(files))
    return hashlib.sha256(joined.encode()).hexdigest()


def download(
    cache_root: Path = CACHE_ROOT,
    refresh: bool = False,
    transport: httpx.BaseTransport | None = None,  # tests pass a mock; never the live source
) -> Path:
    """Fetch the files once per upstream build; returns the snapshot directory."""
    with httpx.Client(timeout=120, follow_redirects=True, transport=transport) as http:
        heads = {}
        for name in FILES:
            url = f"{BASE_URL}{name}.csv.gz"
            r = http.head(url)
            r.raise_for_status()
            heads[name] = {
                "url": url,
                "etag": r.headers.get("etag"),
                "last_modified": r.headers.get("last-modified"),
            }
        built = max(parsedate_to_datetime(h["last_modified"]) for h in heads.values())
        snap_dir = cache_root / built.date().isoformat()
        manifest_path = snap_dir / "manifest.json"
        if manifest_path.exists() and not refresh:
            manifest = json.loads(manifest_path.read_text())
            if all(manifest["files"][n]["etag"] == heads[n]["etag"] for n in FILES):
                log.info("reusing cached snapshot %s", snap_dir.name)
                return snap_dir

        snap_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        for name, head in heads.items():
            target = snap_dir / f"{name}.csv.gz"
            partial = target.with_suffix(".part")
            for attempt in range(4):
                try:
                    with http.stream("GET", head["url"]) as r, partial.open("wb") as fh:
                        r.raise_for_status()
                        for chunk in r.iter_bytes():
                            fh.write(chunk)
                    break
                except httpx.HTTPError:
                    if attempt == 3:
                        raise
                    time.sleep(2**attempt)
            partial.replace(target)  # never leave a half-written file in the cache
            files[name] = {**head, "sha256": sha256_file(target), "bytes": target.stat().st_size}
            if transport is None:
                time.sleep(1)  # one file at a time, gently

        try:
            commit = http.get(COMMIT_URL, headers={"Accept": "application/vnd.github+json"})
            upstream_commit = commit.json()["sha"] if commit.is_success else None
        except (httpx.HTTPError, KeyError, ValueError):
            upstream_commit = None
    manifest = {
        "source": SOURCE,
        "dataset": DATASET,
        "license": "CC0-1.0",
        "files": files,
        "version": snapshot_version(files),
        "upstream_commit": upstream_commit,
        "built_at": built.isoformat(),
        "retrieved_at": datetime.now(UTC).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return snap_dir


# ---------- Parsing ----------


def read_csv_gz(path: Path) -> Iterator[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def parse_date(text: str | None) -> date | None:
    """ "2027-06-30" or "1998-12-17 00:00:00" -> date; blank -> None; else ValueError."""
    text = (text or "").strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


@dataclass(frozen=True)
class TmPlayer:
    tm_id: str
    name: str
    first_name: str
    last_name: str
    birth_date: date | None
    last_season: int | None
    competition_id: str
    club_name: str
    contract_expires: date | None
    club_id: str | None = None


def parse_players(rows: Iterator[dict[str, str]]) -> tuple[list[TmPlayer], list[str]]:
    players, bad = [], []
    for row in rows:
        try:
            players.append(
                TmPlayer(
                    tm_id=row["player_id"].strip(),
                    name=row["name"],
                    first_name=row.get("first_name") or "",
                    last_name=row.get("last_name") or "",
                    birth_date=parse_date(row.get("date_of_birth")),
                    last_season=int(row["last_season"]) if row.get("last_season") else None,
                    competition_id=row.get("current_club_domestic_competition_id") or "",
                    club_name=row.get("current_club_name") or "",
                    contract_expires=parse_date(row.get("contract_expiration_date")),
                    club_id=(row.get("current_club_id") or "").strip() or None,
                )
            )
        except (KeyError, ValueError) as exc:
            bad.append(f"{row.get('player_id')}: {exc!r}")
    return players, bad


# ---------- Linking ----------


def to_person(p: TmPlayer, clubs: dict[str, int]) -> Person:
    """A Transfermarkt player for the matcher: its name, and its first + last name
    when they differ ("Alisson" / "Alisson Becker"); its club when we know it."""
    names = [p.name]
    full = f"{p.first_name} {p.last_name}".strip()
    if full and normalize(full) != normalize(p.name):
        names.append(full)
    club = clubs.get(p.club_id or "")
    return Person(
        p.tm_id,
        tuple(names),
        p.birth_date,
        frozenset({club}) if club else frozenset(),
        p.club_name or None,
    )


# ---------- Loading ----------


PROVENANCE = ("snapshot_id", "ingested_at")


def upsert_changed(session: Session, model, rows: list[dict], constraint: str, keys: tuple) -> int:
    """Insert, or update only where a data value differs. Returns rows written.

    Provenance (snapshot, load time) moves only with a real change, so an
    unchanged row keeps citing the snapshot it first came from.
    """
    written = 0
    table = model.__table__
    for start in range(0, len(rows), BATCH):
        stmt = pg_insert(model).values(rows[start : start + BATCH])
        data_cols = [c for c in rows[0] if c not in keys and c not in PROVENANCE]
        stmt = stmt.on_conflict_do_update(
            constraint=constraint,
            set_={c: stmt.excluded[c] for c in [*data_cols, *PROVENANCE]},
            where=or_(*(table.c[c].is_distinct_from(stmt.excluded[c]) for c in data_cols)),
        )
        written += len(session.execute(stmt.returning(model.id)).all())
    return written


def load_transfermarkt(session: Session, snap_dir: Path) -> dict[str, Any]:
    manifest = json.loads((snap_dir / "manifest.json").read_text())
    now = datetime.now(UTC)

    tm_players, bad_players = parse_players(read_csv_gz(snap_dir / "players.csv.gz"))
    tm_by_id = {p.tm_id: p for p in tm_players}
    # Transfermarkt's latest-season Premier League players: counted when none of
    # ours matches, not queued. The frozen snapshot predates 2026/27, so many
    # have left; the live squads decide who should be ours.
    latest = max((p.last_season for p in tm_players if p.last_season is not None), default=0)
    pl_latest = {
        p.tm_id
        for p in tm_players
        if p.competition_id == PREMIER_LEAGUE and p.last_season == latest
    }
    clubs = club_map(session, SOURCE)  # filled by the live job; club evidence only once known
    matched = resolve(
        session,
        source=SOURCE,
        dataset=DATASET,
        records=[to_person(p, clubs) for p in tm_players],
    )
    links = matched.links
    player_by_tm = {tid: pid for pid, tid in links.items()}

    # Valuations: stream the file, keep linked players, count the rest.
    values, bad_values = [], []
    other_rows = 0
    data_through: date | None = None
    for row in read_csv_gz(snap_dir / "player_valuations.csv.gz"):
        try:
            valued_on = parse_date(row["date"])
            value = int(row["market_value_in_eur"])
            if valued_on is None or value < 0:
                raise ValueError("missing date or negative value")
        except (KeyError, ValueError) as exc:
            bad_values.append(f"{row.get('player_id')} {row.get('date')}: {exc!r}")
            continue
        data_through = max(data_through or valued_on, valued_on)
        pid = player_by_tm.get(row["player_id"].strip())
        if pid is None:
            other_rows += 1
            continue
        values.append(
            {
                "player_id": pid,
                "source": SOURCE,
                "valued_on": valued_on,
                "value_eur": value,
                "club_name": row.get("current_club_name") or None,
                "competition_id": row.get("player_club_domestic_competition_id") or None,
            }
        )

    # The snapshot row (one per version), then everything that cites it.
    snapshot = session.scalar(
        select(SourceSnapshot).where(
            SourceSnapshot.source == SOURCE, SourceSnapshot.version == manifest["version"]
        )
    )
    if snapshot is None:
        snapshot = SourceSnapshot(
            source=SOURCE,
            dataset=manifest["dataset"],
            version=manifest["version"],
            files=manifest["files"],
            upstream_commit=manifest.get("upstream_commit"),
            built_at=datetime.fromisoformat(manifest["built_at"]),
            data_through=data_through,
            retrieved_at=datetime.fromisoformat(manifest["retrieved_at"]),
        )
        session.add(snapshot)
        session.flush()
    matched.run.snapshot_id = snapshot.id

    # The live API (app.ingest.transfermarkt_api) is newer than this frozen
    # snapshot: a value it wrote for a date is never overwritten from here.
    live = {
        (pid, day)
        for pid, day in session.execute(
            select(PlayerMarketValue.player_id, PlayerMarketValue.valued_on)
            .join(SourceSnapshot, SourceSnapshot.id == PlayerMarketValue.snapshot_id)
            .where(PlayerMarketValue.source == SOURCE, SourceSnapshot.dataset == LIVE_DATASET)
        )
    }
    kept_live = sum(1 for v in values if (v["player_id"], v["valued_on"]) in live)
    values = [v for v in values if (v["player_id"], v["valued_on"]) not in live]
    for v in values:
        v.update(snapshot_id=snapshot.id, ingested_at=now)
    values_written = (
        upsert_changed(
            session,
            PlayerMarketValue,
            values,
            "uq_player_market_values_player_source_date",
            ("player_id", "source", "valued_on"),
        )
        if values
        else 0
    )

    contracts, no_contract = [], []
    missing_from_snapshot = 0
    for pid, tid in links.items():
        p = tm_by_id.get(tid)
        if p is None:
            missing_from_snapshot += 1
            continue
        if p.contract_expires is None:
            no_contract.append(p.name)
            continue
        contracts.append(
            {
                "player_id": pid,
                "source": SOURCE,
                "expires_on": p.contract_expires,
                "club_name": p.club_name or None,
                "snapshot_id": snapshot.id,
                "ingested_at": now,
            }
        )
    contracts_written = (
        upsert_changed(
            session,
            PlayerContract,
            contracts,
            "uq_player_contracts_player_source",
            ("player_id", "source"),
        )
        if contracts
        else 0
    )
    session.flush()

    valued = {v["player_id"] for v in values}
    if bad_players or bad_values:
        log.warning(
            "unreadable rows: %d players, %d valuations, e.g. %s",
            len(bad_players),
            len(bad_values),
            "; ".join((bad_players + bad_values)[:5]),
        )
    counts = matched.counts

    return {
        "snapshot_version": manifest["version"][:12],
        "upstream_commit": (manifest.get("upstream_commit") or "unknown")[:12],
        "data_through": data_through.isoformat() if data_through else None,
        "our_players": counts["our_players"],
        "linked": len(links),
        "linked_new": len(matched.new_links),
        "link_methods": counts["new_by_method"],
        "unlinked": counts["unmatched_our_players"],
        "linked_missing_from_snapshot": missing_from_snapshot,
        "unreadable_players": len(bad_players),
        "unreadable_valuations": len(bad_values),
        "valuations_for_our_players": len(values),
        "valuations_written": values_written,
        "valuations_kept_from_live_api": kept_live,
        "valuations_other_players": other_rows,
        "linked_without_valuations": len(set(links) - valued),
        "contracts_for_our_players": len(contracts),
        "contracts_written": contracts_written,
        "linked_without_contract_date": len(no_contract),
        "tm_pl_players_not_ours": len(pl_latest - set(links.values())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="download the files again")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    snap_dir = download(CACHE_ROOT, refresh=args.refresh)
    with SessionLocal() as session, session.begin():
        summary = load_transfermarkt(session, snap_dir)
    log.info("loaded: %s", summary)


if __name__ == "__main__":
    main()
