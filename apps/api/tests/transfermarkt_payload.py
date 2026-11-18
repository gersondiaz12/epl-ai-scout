"""A tiny Transfermarkt snapshot, shaped like dcaribou/transfermarkt-datasets
(only the columns the loader reads). Written to a temp folder as gzipped CSV,
because the repo ignores *.csv files.

Our players come from tests/fpl_payload.py:
Striker 2000-01-15, Mover 1998-06-01, Keeper (no birth date), Forward 1995-03-03.

- 101 Striker Test: same birth date and name -> linked; contract 2028-06-30.
- 102 Mover Test: linked; no contract date in the source.
- 103 Keeper Test: ours has no birth date; unique exact name, active -> linked by name.
- 104 Someone Else: shares Forward's birth date only -> Forward is not in the dataset.
- 105 Old Legend: last club in the Premier League, but retired (2010) -> not reported.
- 106 Other Squad: 2025/26 Premier League player who isn't one of ours -> reported.
"""

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any

PLAYER_COLUMNS = [
    "player_id",
    "first_name",
    "last_name",
    "name",
    "last_season",
    "date_of_birth",
    "contract_expiration_date",
    "current_club_domestic_competition_id",
    "current_club_name",
]


def player(pid, first, last, dob, contract="", comp="GB1", club="Arsenal FC", season="2025"):
    return {
        "player_id": pid,
        "first_name": first,
        "last_name": last,
        "name": f"{first} {last}",
        "last_season": season,
        "date_of_birth": f"{dob} 00:00:00" if dob else "",
        "contract_expiration_date": contract,
        "current_club_domestic_competition_id": comp,
        "current_club_name": club,
    }


PLAYERS = [
    player("101", "Striker", "Test", "2000-01-15", "2028-06-30"),
    player("102", "Mover", "Test", "1998-06-01"),
    player("103", "Keeper", "Test", "1990-01-01", "2027-06-30", club="Coventry City"),
    player("104", "Someone", "Else", "1995-03-03", comp="ES1", club="Real Betis"),
    player("105", "Old", "Legend", "1980-05-05", season="2010"),
    player("106", "Other", "Squad", "1999-09-09", "2029-06-30"),
]

VALUATION_COLUMNS = [
    "player_id",
    "date",
    "market_value_in_eur",
    "current_club_name",
    "current_club_id",
    "player_club_domestic_competition_id",
]


def valuation(pid, day, value, club="Arsenal FC", comp="GB1"):
    return {
        "player_id": pid,
        "date": day,
        "market_value_in_eur": value,
        "current_club_name": club,
        "current_club_id": "11",
        "player_club_domestic_competition_id": comp,
    }


VALUATIONS = [
    valuation("101", "2024-06-01", "50000000", club="Benfica", comp="PO1"),
    valuation("101", "2025-12-01", "60000000"),
    valuation("102", "2025-06-12", "8000000"),
    valuation("106", "2026-06-12", "1000000"),  # not one of ours
    valuation("101", "2026-01-01", "not-a-number"),  # unreadable
]


def gz_csv(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=columns, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(rows)
    return gzip.compress(text.getvalue().encode(), mtime=0)


def files(players=None, valuations=None) -> dict[str, bytes]:
    return {
        "players": gz_csv(PLAYERS if players is None else players, PLAYER_COLUMNS),
        "player_valuations": gz_csv(
            VALUATIONS if valuations is None else valuations, VALUATION_COLUMNS
        ),
    }


def write_snapshot(folder: Path, data: dict[str, bytes] | None = None) -> Path:
    """A snapshot folder as download() leaves it: the files plus manifest.json."""
    from app.ingest.transfermarkt import snapshot_version

    folder.mkdir(parents=True, exist_ok=True)
    meta = {}
    for name, blob in (data or files()).items():
        (folder / f"{name}.csv.gz").write_bytes(blob)
        meta[name] = {"sha256": hashlib.sha256(blob).hexdigest(), "etag": f'"{name}-1"'}
    manifest = {
        "source": "transfermarkt",
        "dataset": "dcaribou/transfermarkt-datasets",
        "license": "CC0-1.0",
        "files": meta,
        "version": snapshot_version(meta),
        "upstream_commit": "e44f186d6f06dd8452aaf54c7921ba66c961f637",
        "built_at": "2026-09-05T09:12:22+00:00",
        "retrieved_at": "2026-11-17T20:00:00+00:00",
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    return folder
