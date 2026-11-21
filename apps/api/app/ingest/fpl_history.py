"""Load past seasons from FPL's per-player history into player_season_totals.

    uv run python -m app.ingest.fpl_history              # the 3 seasons before the current one
    uv run python -m app.ingest.fpl_history --seasons 2
    uv run python -m app.ingest.fpl_history --refresh    # ignore today's cached responses

Run after `app.ingest.fpl`, which creates the current season and links every
player to FPL's stable code. Each player's `element-summary` holds
`history_past`: one season total per player, with no club split and no
appearances. Rows are linked to our players through player_source_ids by
`element_code`; anything that can't be linked is counted and logged, never
dropped silently.

FPL's history covers only players still in the game, so players who have left
the Premier League have no past rows here.
"""

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.identity.matcher import record_exact_run
from app.ingest.fpl import CACHE_ROOT, SOURCE, FplClient
from app.models import PlayerSeasonTotals, PlayerSourceId, Season

log = logging.getLogger("ingest.fpl_history")

Json = dict[str, Any]

# Our column -> FPL history_past key.
FIELDS: dict[str, str] = {
    "minutes": "minutes",
    "starts": "starts",
    "goals": "goals_scored",
    "assists": "assists",
    "xg": "expected_goals",
    "xa": "expected_assists",
    "xg_conceded": "expected_goals_conceded",
    "saves": "saves",
    "tackles": "tackles",
    "cbi": "clearances_blocks_interceptions",
    "recoveries": "recoveries",
    "goals_conceded": "goals_conceded",
    "clean_sheets": "clean_sheets",
    "penalties_saved": "penalties_saved",
}
DECIMAL_FIELDS = {"xg", "xa", "xg_conceded"}
# Fields FPL added in later seasons; before that it reports 0 for everyone. A
# season where all players have 0 for one of these didn't track it, so it is
# stored as null. Long-standing fields keep real zeros (a season can genuinely
# have no penalty saves among current players).
LATER_FIELDS = {"starts", "xg", "xa", "xg_conceded", "tackles", "cbi", "recoveries"}


def fpl_season_label(name: str) -> str:
    """FPL's "2024/25" -> our "2024-25"."""
    return name.replace("/", "-")


def previous_labels(current: str, count: int) -> list[str]:
    """The `count` seasons before `current`, newest first.

    "2026-27", 3 -> ["2025-26", "2024-25", "2023-24"].
    """
    start = int(current[:4])
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(start - 1, start - 1 - count, -1)]


def parse_value(column: str, raw: Any) -> int | Decimal:
    """One FPL value as stored; raises ValueError when it isn't a valid non-negative number."""
    if raw is None or isinstance(raw, bool):
        raise ValueError(f"{column}={raw!r}")
    try:
        value = Decimal(str(raw)) if column in DECIMAL_FIELDS else int(raw)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{column}={raw!r}") from None
    if (isinstance(value, Decimal) and not value.is_finite()) or value < 0:
        raise ValueError(f"{column}={raw!r}")
    return value


@dataclass
class PastRow:
    element_code: int
    season: str  # our label
    values: dict[str, int | Decimal | None]


@dataclass
class Parsed:
    rows: list[PastRow] = field(default_factory=list)
    out_of_range: int = 0  # seasons outside the requested ones (by design)
    unparseable: list[str] = field(default_factory=list)
    untracked: dict[str, list[str]] = field(default_factory=dict)  # season -> fields nulled


def parse_history(summaries: list[Json], seasons: list[str]) -> Parsed:
    """Pick the requested seasons out of every player's history_past."""
    parsed = Parsed()
    for summary in summaries:
        for h in summary.get("history_past", []):
            label = fpl_season_label(h.get("season_name", ""))
            if label not in seasons:
                parsed.out_of_range += 1
                continue
            try:
                values = {col: parse_value(col, h.get(key)) for col, key in FIELDS.items()}
                code = int(h["element_code"])
            except (ValueError, KeyError, TypeError) as exc:
                parsed.unparseable.append(f"{h.get('element_code')} {label}: {exc}")
                continue
            parsed.rows.append(PastRow(element_code=code, season=label, values=values))

    for season in seasons:
        in_season = [r for r in parsed.rows if r.season == season]
        nulled = sorted(
            col for col in LATER_FIELDS if in_season and all(r.values[col] == 0 for r in in_season)
        )
        if nulled:
            parsed.untracked[season] = nulled
            for r in in_season:
                for col in nulled:
                    r.values[col] = None
    return parsed


def load_history(session: Session, summaries: list[Json], count: int = 3) -> dict[str, Any]:
    current = session.scalar(select(Season).where(Season.is_current))
    if current is None:
        raise RuntimeError("No current season. Run `python -m app.ingest.fpl` first.")
    seasons = previous_labels(current.label, count)
    parsed = parse_history(summaries, seasons)

    # Past seasons: created by label only. FPL's history gives no dates, so none are guessed.
    season_ids: dict[str, int] = {}
    for label in seasons:
        season = session.scalar(select(Season).where(Season.label == label))
        if season is None:
            season = Season(label=label, start_date=None, end_date=None, is_current=False)
            session.add(season)
            session.flush()
        season_ids[label] = season.id

    player_by_code = {
        int(sid.external_id): sid.player_id
        for sid in session.scalars(select(PlayerSourceId).where(PlayerSourceId.source == SOURCE))
    }
    values: list[dict[str, Any]] = []
    unlinked: list[str] = []
    for r in parsed.rows:
        player_id = player_by_code.get(r.element_code)
        if player_id is None:
            unlinked.append(f"{r.element_code} {r.season}")
            continue
        key = {"player_id": player_id, "season_id": season_ids[r.season], "source": SOURCE}
        values.append({**key, **r.values})

    if values:
        stmt = pg_insert(PlayerSeasonTotals).values(values)
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_player_season_totals_player_season_source",
                set_={
                    **{col: stmt.excluded[col] for col in FIELDS},
                    "ingested_at": func.now(),
                },
            )
        )
    # Past seasons are closed, so rows FPL no longer lists (a player who left the
    # game) stay true. They are kept and counted, not deleted.
    seen = {(v["player_id"], v["season_id"]) for v in values}
    kept = [
        row
        for row in session.execute(
            select(PlayerSeasonTotals.player_id, PlayerSeasonTotals.season_id).where(
                PlayerSeasonTotals.source == SOURCE,
                PlayerSeasonTotals.season_id.in_(season_ids.values()),
            )
        )
        if (row.player_id, row.season_id) not in seen
    ]
    session.flush()

    if unlinked:
        log.warning(
            "%d rows have no matching player (FPL code not in player_source_ids), e.g.: %s",
            len(unlinked),
            ", ".join(unlinked[:10]),
        )
    if parsed.unparseable:
        log.warning(
            "%d rows skipped with unreadable values, e.g.:\n%s",
            len(parsed.unparseable),
            "\n".join(parsed.unparseable[:10]),
        )
    for season, cols in parsed.untracked.items():
        log.info("%s: FPL didn't track %s that season; stored as null", season, ", ".join(cols))

    record_exact_run(
        session,
        source=SOURCE,
        dataset="fpl/element-summary history_past",
        counts={
            "records": len(values) + len(unlinked),
            "records_in_scope": len(values) + len(unlinked),
            "linked": len(values),
            "unmatched_records": {"code_not_ours": len(unlinked)} if unlinked else {},
        },
    )
    return {
        "seasons": seasons,
        "rows_by_season": {
            s: sum(1 for v in values if v["season_id"] == season_ids[s]) for s in seasons
        },
        "linked": len(values),
        "unlinked": len(unlinked),
        "unparseable": len(parsed.unparseable),
        "out_of_range_rows": parsed.out_of_range,
        "zero_minute_rows": sum(1 for v in values if v["minutes"] == 0),
        "kept_not_in_source": len(kept),
        "untracked": parsed.untracked,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seasons", type=int, default=3, help="how many past seasons (default 3)")
    parser.add_argument("--refresh", action="store_true", help="ignore today's cached responses")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    client = FplClient(CACHE_ROOT / date.today().isoformat(), refresh=args.refresh)
    elements = client.get("/bootstrap-static/")["elements"]
    log.info("reading history for all %d players (cached responses are reused)", len(elements))
    with ThreadPoolExecutor(max_workers=5) as pool:
        summaries = list(pool.map(lambda e: client.get(f"/element-summary/{e['id']}/"), elements))
    with SessionLocal() as session, session.begin():
        summary = load_history(session, summaries, args.seasons)
    log.info("loaded: %s", summary)


if __name__ == "__main__":
    main()
