"""Match rate per source, from the latest runs and the stored links.

uv run python -m app.identity.report
"""

from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.identity.resolve import open_records
from app.models import MatchRun, Player, PlayerSeasonStats, PlayerSourceId, Season


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.1f}%)" if d else f"{n}/0"


def report(session: Session) -> dict:
    out: dict = {"datasets": [], "links": {}}
    datasets = session.execute(
        select(MatchRun.source, MatchRun.dataset).distinct().order_by(MatchRun.source)
    ).all()
    for source, dataset in datasets:
        runs = list(
            session.scalars(
                select(MatchRun)
                .where(MatchRun.source == source, MatchRun.dataset == dataset)
                .order_by(MatchRun.id.desc())
                .limit(2)
            )
        )
        latest, previous = runs[0], (runs[1] if len(runs) > 1 else None)
        c = latest.counts
        entry = {
            "source": source,
            "dataset": dataset,
            "run": latest.id,
            "at": latest.finished_at.isoformat(timespec="minutes"),
            "records": c.get("records"),
            "records_in_scope": c.get("records_in_scope"),
            "our_players": c.get("our_players"),
            "linked": c.get("linked"),
            "new_by_method": c.get("new_by_method", {}),
            "unmatched_our_players": c.get("unmatched_our_players", {}),
            "source_records_not_ours": c.get("source_records_not_ours"),
        }
        if previous:
            entry["linked_change"] = (c.get("linked") or 0) - (previous.counts.get("linked") or 0)
        out["datasets"].append(entry)

    players = session.scalar(select(func.count()).select_from(Player))
    current = set(
        session.scalars(
            select(PlayerSeasonStats.player_id)
            .join(Season, Season.id == PlayerSeasonStats.season_id)
            .where(Season.is_current)
        )
    )
    for source in session.scalars(select(PlayerSourceId.source).distinct()):
        rows = session.execute(
            select(PlayerSourceId.player_id, PlayerSourceId.method, PlayerSourceId.score).where(
                PlayerSourceId.source == source
            )
        ).all()
        fuzzy = sorted(float(s) for _, m, s in rows if m == "fuzzy" and s is not None)
        now = datetime.now(UTC)
        opened = open_records(session, source)
        out["links"][source] = {
            "players_linked": pct(len(rows), players),
            "current_season_players_linked": pct(
                sum(1 for pid, _, _ in rows if pid in current), len(current)
            ),
            "by_method": dict(Counter(m for _, m, _ in rows)),
            "fuzzy_scores": fuzzy,
            "open_unmatched": dict(Counter(r.reason for r in opened)),
            "oldest_open_days": max(
                (
                    (now - session.get(MatchRun, r.first_seen_run_id).started_at).days
                    for r in opened
                ),
                default=0,
            ),
        }
    return out


def main() -> None:
    with SessionLocal() as session:
        r = report(session)
    for d in r["datasets"]:
        print(f"\n{d['source']} / {d['dataset']}  (run {d['run']}, {d['at']})")
        if d["records_in_scope"]:
            print(
                "  in-scope records linked:",
                pct(
                    d["records_in_scope"] - (d["source_records_not_ours"] or 0),
                    d["records_in_scope"],
                ),
            )
        if d["our_players"]:
            print("  our players linked:     ", pct(d["linked"], d["our_players"]))
        else:
            print("  records linked:         ", pct(d["linked"] or 0, d["records"] or 0))
        if d.get("linked_change"):
            print("  change since last run:  ", f"{d['linked_change']:+d}")
        if d["new_by_method"]:
            print("  new links by method:    ", d["new_by_method"])
        if d["unmatched_our_players"]:
            print("  unmatched (ours):       ", d["unmatched_our_players"])
    for source, s in r["links"].items():
        print(f"\nlinks: {source}")
        for k, v in s.items():
            if v or v == 0:
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
