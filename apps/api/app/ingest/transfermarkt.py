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
2. Link Transfermarkt players to ours (the Premier League players we hold) by
   birth date plus a shared name word, accent-insensitive. Links are stored in
   player_source_ids and kept on later runs.
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
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Player, PlayerContract, PlayerMarketValue, PlayerSourceId, SourceSnapshot
from app.text import normalize

log = logging.getLogger("ingest.transfermarkt")

SOURCE = "transfermarkt"
DATASET = "dcaribou/transfermarkt-datasets"
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


def name_words(*names: str | None) -> set[str]:
    """Normalised words of 3+ letters, so particles like "de" or "da" can't link two people."""
    return {w for n in names if n for w in normalize(n).split() if len(w) >= 3}


SIMILAR_WORD_RATIO = 0.8  # Yarmoliuk/Yarmolyuk 0.89, Savio/Savinho 0.83


def similar_words(a: set[str], b: set[str]) -> bool:
    """Any pair of 4+ letter words at least SIMILAR_WORD_RATIO alike."""
    return any(
        SequenceMatcher(None, x, y).ratio() >= SIMILAR_WORD_RATIO
        for x in a
        for y in b
        if len(x) >= 4 and len(y) >= 4
    )


@dataclass(frozen=True)
class Ours:
    id: int
    name: str
    display_name: str
    birth_date: date | None


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
                )
            )
        except (KeyError, ValueError) as exc:
            bad.append(f"{row.get('player_id')}: {exc!r}")
    return players, bad


# ---------- Linking ----------


@dataclass
class Matches:
    links: dict[int, str] = field(default_factory=dict)  # our player id -> transfermarkt id
    methods: Counter = field(default_factory=Counter)
    unlinked: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))


def match_players(ours: list[Ours], tm: list[TmPlayer]) -> Matches:
    """Link each of our players to at most one Transfermarkt player.

    With a birth date: candidates share the date and at least one name word
    (3+ letters); the one sharing the most words wins, and a tie is ambiguous.
    If none shares a word, one candidate with a similar word (spelling
    variant, e.g. Yarmoliuk / Yarmolyuk) links; more than one is ambiguous.
    Without one: the normalised full name must equal exactly one recently
    active Transfermarkt player's name. A Transfermarkt player claimed by two
    of ours links neither.
    """
    by_dob: dict[date, list[TmPlayer]] = defaultdict(list)
    for p in tm:
        if p.birth_date:
            by_dob[p.birth_date].append(p)
    latest = max((p.last_season for p in tm if p.last_season is not None), default=0)
    by_name: dict[str, list[TmPlayer]] = defaultdict(list)
    for p in tm:
        if p.last_season is not None and p.last_season >= latest - 1:
            by_name[normalize(p.name)].append(p)

    m = Matches()
    for o in ours:
        label = f"{o.name} ({o.id})"
        if o.birth_date is None:
            found = {
                p.tm_id: p
                for n in {normalize(o.name), normalize(o.display_name)}
                for p in by_name.get(n, [])
            }
            if len(found) == 1:
                m.links[o.id] = next(iter(found))
                m.methods["name_only"] += 1
            else:
                m.unlinked["no_birth_date" if not found else "ambiguous"].append(label)
            continue
        candidates = by_dob.get(o.birth_date, [])
        if not candidates:
            m.unlinked["no_birth_date_match"].append(label)
            continue
        ours_words = name_words(o.name, o.display_name)
        scored = [
            (len(ours_words & name_words(p.name, p.first_name, p.last_name)), p) for p in candidates
        ]
        scored = [(score, p) for score, p in scored if score > 0]
        if not scored:
            # Spelling variants of the same name (transliteration, nicknames):
            # only between players who already share a birth date.
            similar = [
                p
                for p in candidates
                if similar_words(ours_words, name_words(p.name, p.first_name, p.last_name))
            ]
            if len(similar) == 1:
                m.links[o.id] = similar[0].tm_id
                m.methods["birth_date_and_similar_name"] += 1
            elif similar:
                m.unlinked["ambiguous"].append(label)
            else:
                # The players sharing the birth date are other people: ours
                # isn't in the dataset (it covers mainly top-division leagues).
                m.unlinked["not_in_dataset"].append(label)
            continue
        best = max(score for score, _ in scored)
        top = [p for score, p in scored if score == best]
        if len(top) > 1:
            m.unlinked["ambiguous"].append(label)
            continue
        m.links[o.id] = top[0].tm_id
        m.methods["birth_date_and_name"] += 1

    claimed = Counter(m.links.values())
    for our_id, tm_id in list(m.links.items()):
        if claimed[tm_id] > 1:
            del m.links[our_id]
            m.unlinked["same_transfermarkt_player"].append(str(our_id))
    return m


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

    # Our players: every Premier League player we hold.
    ours = [
        Ours(p.id, p.name, p.display_name, p.birth_date) for p in session.scalars(select(Player))
    ]
    tm_players, bad_players = parse_players(read_csv_gz(snap_dir / "players.csv.gz"))
    tm_by_id = {p.tm_id: p for p in tm_players}

    # Existing links win: they are stable ids and may have been checked by hand.
    existing = {
        sid.player_id: sid.external_id
        for sid in session.scalars(select(PlayerSourceId).where(PlayerSourceId.source == SOURCE))
    }
    matches = match_players([o for o in ours if o.id not in existing], tm_players)
    taken = set(existing.values())
    new_links = {pid: tid for pid, tid in matches.links.items() if tid not in taken}
    for pid in set(matches.links) - set(new_links):
        matches.unlinked["already_linked_to_another_player"].append(str(pid))
    for pid, tid in new_links.items():
        session.add(PlayerSourceId(player_id=pid, source=SOURCE, external_id=tid))
    links = {**existing, **new_links}
    player_by_tm = {tid: pid for pid, tid in links.items()}
    session.flush()

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
    for pid, tid in links.items():
        p = tm_by_id.get(tid)
        if p is None:
            matches.unlinked["linked_player_missing_from_snapshot"].append(str(pid))
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

    # Transfermarkt's 2025/26 Premier League players that none of ours matched
    # (left the league, not in FPL, or a matching miss): reported, not loaded.
    latest = max((p.last_season for p in tm_players if p.last_season is not None), default=0)
    linked_tm = set(links.values())
    pl_not_linked = [
        p
        for p in tm_players
        if p.competition_id == PREMIER_LEAGUE
        and p.last_season == latest
        and p.tm_id not in linked_tm
    ]
    valued = {v["player_id"] for v in values}

    unlinked = {reason: len(items) for reason, items in matches.unlinked.items() if items}
    for reason, items in matches.unlinked.items():
        if items:
            log.warning("unlinked (%s): %d, e.g. %s", reason, len(items), ", ".join(items[:5]))
    if bad_players or bad_values:
        log.warning(
            "unreadable rows: %d players, %d valuations, e.g. %s",
            len(bad_players),
            len(bad_values),
            "; ".join((bad_players + bad_values)[:5]),
        )
    if pl_not_linked:
        log.info(
            "%d Transfermarkt %d/%02d Premier League players match none of ours, e.g. %s",
            len(pl_not_linked),
            latest,
            (latest + 1) % 100,
            ", ".join(p.name for p in pl_not_linked[:8]),
        )

    return {
        "snapshot_version": manifest["version"][:12],
        "upstream_commit": (manifest.get("upstream_commit") or "unknown")[:12],
        "data_through": data_through.isoformat() if data_through else None,
        "our_players": len(ours),
        "linked": len(links),
        "linked_new": len(new_links),
        "link_methods": dict(matches.methods),
        "unlinked": unlinked,
        "unreadable_players": len(bad_players),
        "unreadable_valuations": len(bad_values),
        "valuations_for_our_players": len(values),
        "valuations_written": values_written,
        "valuations_other_players": other_rows,
        "linked_without_valuations": len(set(links) - valued),
        "contracts_for_our_players": len(contracts),
        "contracts_written": contracts_written,
        "linked_without_contract_date": len(no_contract),
        "tm_pl_players_not_ours": len(pl_not_linked),
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
