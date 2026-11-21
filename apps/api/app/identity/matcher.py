"""Resolve one source's records to our players and store the evidence.

    run = resolve(session, source="transfermarkt", dataset=..., records=[...])

Writes, inside the caller's transaction:
- player_source_ids: new links (method, score, run, time); manual links are
  never touched; a stored automatic link is kept, and relabelled from
  "legacy" when a rule supports it, never changed;
- unmatched_records: every one of our players still without a link, and every
  in-scope source record without one of ours, with candidates and a reason;
- match_runs: settings and counts.
Manual decisions (player_match_decisions) are applied first and only read.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.identity.stages import Person, assign, candidate_entry, evaluate, settings
from app.models import (
    MatchRun,
    Player,
    PlayerContract,
    PlayerMarketValue,
    PlayerMatchDecision,
    PlayerSeasonStats,
    PlayerSourceId,
    Season,
    UnmatchedRecord,
)

log = logging.getLogger("identity")


@dataclass
class RunResult:
    run: MatchRun
    links: dict[int, str]  # our player id -> external id, after the run
    new_links: dict[int, str]
    dropped: set[int]  # players whose link was removed by a decision (their rows were cleared)
    counts: dict = field(default_factory=dict)


# ---------- Our players ----------


def our_people(session: Session) -> dict[int, Person]:
    """Every player we hold, with all their clubs this season (a transferred
    player keeps the club they left, so evidence from either club counts)."""
    clubs: dict[int, set[int]] = {}
    rows = session.execute(
        select(PlayerSeasonStats.player_id, PlayerSeasonStats.club_id)
        .join(Season, Season.id == PlayerSeasonStats.season_id)
        .where(Season.is_current)
    )
    for pid, cid in rows:
        clubs.setdefault(pid, set()).add(cid)
    return {
        p.id: Person(str(p.id), (p.name,), p.birth_date, frozenset(clubs.get(p.id, ())))
        for p in session.scalars(select(Player).order_by(Player.id))
    }


# ---------- Stage 0: manual decisions ----------


def active_decisions(session: Session, source: str) -> list[PlayerMatchDecision]:
    return list(
        session.scalars(
            select(PlayerMatchDecision)
            .where(
                PlayerMatchDecision.source == source, PlayerMatchDecision.superseded_by.is_(None)
            )
            .order_by(PlayerMatchDecision.id)
        )
    )


def drop_source_rows(session: Session, source: str, player_ids: set[int]) -> None:
    """Rows loaded through a link that an operator removed belong to someone else."""
    if not player_ids:
        return
    for model in (PlayerMarketValue, PlayerContract):
        session.execute(
            delete(model).where(model.source == source, model.player_id.in_(player_ids))
        )


def apply_decisions(session: Session, source: str, now: datetime) -> set[int]:
    """Make the stored links agree with the active decisions. Returns players
    whose link was removed or moved (their source rows are cleared)."""
    dropped: set[int] = set()
    links = {
        s.player_id: s
        for s in session.scalars(select(PlayerSourceId).where(PlayerSourceId.source == source))
    }
    decisions = active_decisions(session, source)
    # A manual link whose decision was withdrawn or superseded is no longer protected.
    backed = {(d.player_id, d.external_id) for d in decisions if d.decision == "link"}
    for pid, row in list(links.items()):
        if row.method == "manual" and (pid, row.external_id) not in backed:
            dropped.add(pid)
            session.delete(row)
            del links[pid]
    session.flush()
    by_ext = {s.external_id: s for s in links.values()}
    for d in decisions:
        if d.decision == "link":
            holder = by_ext.get(d.external_id)
            if holder is not None and holder.player_id != d.player_id:
                dropped.add(holder.player_id)
                session.delete(holder)
                links.pop(holder.player_id, None)
                session.flush()
            row = links.get(d.player_id)
            if row is None:
                row = PlayerSourceId(
                    player_id=d.player_id, source=source, external_id=d.external_id
                )
                session.add(row)
                links[d.player_id] = row
            elif row.external_id != d.external_id:
                dropped.add(d.player_id)
                row.external_id = d.external_id
            if row.method != "manual":
                row.method, row.score, row.matched_at = "manual", None, now
            by_ext[d.external_id] = row
        elif d.decision == "reject":
            row = links.get(d.player_id)
            if row is not None and row.external_id == d.external_id and row.method != "manual":
                dropped.add(d.player_id)
                session.delete(row)
                links.pop(d.player_id)
                by_ext.pop(d.external_id, None)
        elif d.decision == "no_match" and d.player_id is not None:
            row = links.get(d.player_id)
            if row is not None and row.method != "manual":
                dropped.add(d.player_id)
                session.delete(row)
                links.pop(d.player_id)
                by_ext.pop(row.external_id, None)
    session.flush()
    drop_source_rows(session, source, dropped)
    return dropped


# ---------- The run ----------


def resolve(
    session: Session,
    *,
    source: str,
    dataset: str,
    records: list[Person],
    in_scope=lambda rec: False,  # source records that should be ours (queued when unmatched)
    snapshot_id: int | None = None,
) -> RunResult:
    started = datetime.now(UTC)
    dropped = apply_decisions(session, source, started)
    decisions = active_decisions(session, source)
    rejected = {(str(d.player_id), d.external_id) for d in decisions if d.decision == "reject"}
    closed_players = {d.player_id for d in decisions if d.decision == "no_match" and d.player_id}
    closed_records = {
        d.external_id for d in decisions if d.decision == "no_match" and d.external_id
    }

    people = our_people(session)
    by_key = {r.key: r for r in records}
    stored = {
        s.player_id: s
        for s in session.scalars(select(PlayerSourceId).where(PlayerSourceId.source == source))
    }

    run = MatchRun(
        source=source,
        dataset=dataset,
        snapshot_id=snapshot_id,
        matcher_version=settings()["matcher_version"],
        settings=settings(),
        counts={},
        started_at=started,
        finished_at=started,
    )
    session.add(run)
    session.flush()

    unmatched: dict[str, dict] = {}  # record_key -> row values

    def queue(side, reason, cands, *, player=None, rec=None):
        ext = rec.key if rec else None
        pid = int(player.key) if player else None
        person = player or rec
        unmatched[f"{side}:{ext or ''}:{pid or ''}"] = {
            "side": side,
            "external_id": ext,
            "player_id": pid,
            "name": person.label[:200],
            "birth_date": person.birth_date,
            "club_name": person.club_name,
            "reason": reason,
            "candidates": cands,
        }

    # Stage 1: stored links are kept. Legacy ones get the rule that supports them.
    relabelled = conflicts = unsupported = 0
    for pid, row in stored.items():
        rec = by_key.get(row.external_id)
        if rec is None or pid not in people:
            continue
        ev = evaluate(people[pid], rec)
        if ev.failed_on == "different_birth_date" and row.method != "manual":
            conflicts += 1
            queue(
                "our_player",
                "conflict_with_existing_link",
                [candidate_entry(rec, ev)],
                player=people[pid],
            )
        if row.method == "legacy":
            if ev.rank > 0:
                row.method = ev.method
                row.score = Decimal(f"{ev.score:.3f}") if ev.method == "fuzzy" else None
                row.match_run_id, row.matched_at = run.id, started
                relabelled += 1
            else:
                unsupported += 1

    # Stages 2-4 for everyone else.
    linked_records = {row.external_id for row in stored.values()}
    todo = [p for pid, p in people.items() if pid not in stored and pid not in closed_players]
    pool = [r for r in records if r.key not in closed_records]
    result = assign(todo, pool, taken=linked_records, rejected=rejected)
    new_links: dict[int, str] = {}
    methods: Counter = Counter()
    for o_key, (r_key, ev) in sorted(result.links.items()):
        pid = int(o_key)
        session.add(
            PlayerSourceId(
                player_id=pid,
                source=source,
                external_id=r_key,
                method=ev.method,
                score=Decimal(f"{ev.score:.3f}") if ev.method == "fuzzy" else None,
                match_run_id=run.id,
                matched_at=started,
            )
        )
        new_links[pid] = r_key
        methods[ev.method] += 1
    for o_key, (reason, cands) in result.unmatched.items():
        queue("our_player", reason, cands, player=people[int(o_key)])
    session.flush()

    links = {pid: row.external_id for pid, row in stored.items()} | new_links
    linked = set(links.values())
    not_ours = 0
    for rec in records:
        if rec.key in linked or rec.key in closed_records or not in_scope(rec):
            continue
        not_ours += 1
        same_dob = [p for p in people.values() if rec.birth_date and p.birth_date == rec.birth_date]
        cands = [candidate_entry(p, evaluate(p, rec)) for p in same_dob[:5]]
        queue("source_record", "source_record_not_ours", cands, rec=rec)

    # The queue: upsert what's open now; rows not seen this run stay as history.
    for key, values in unmatched.items():
        stmt = pg_insert(UnmatchedRecord).values(
            source=source,
            dataset=dataset,
            record_key=key,
            first_seen_run_id=run.id,
            last_seen_run_id=run.id,
            **values,
        )
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_unmatched_records_source_dataset_key",
                set_={**{k: stmt.excluded[k] for k in values}, "last_seen_run_id": run.id},
            )
        )

    reasons = Counter(v["reason"] for v in unmatched.values() if v["side"] == "our_player")
    all_methods = Counter(
        s.method
        for s in session.scalars(select(PlayerSourceId).where(PlayerSourceId.source == source))
    )
    run.counts = {
        "our_players": len(people),
        "records": len(records),
        "records_in_scope": sum(1 for r in records if in_scope(r)),
        "linked": len(links),
        "linked_new": len(new_links),
        "new_by_method": dict(methods),
        "links_by_method": dict(all_methods),
        "legacy_relabelled": relabelled,
        "legacy_without_rule_support": unsupported,
        "conflicts_with_existing_link": conflicts,
        "unmatched_our_players": dict(reasons),
        "source_records_not_ours": not_ours,
        "manual_decisions_active": len(decisions),
        "links_dropped_by_decision": len(dropped),
    }
    run.finished_at = datetime.now(UTC)
    session.flush()
    for reason, n in reasons.items():
        log.debug("unmatched (%s): %d", reason, n)
    return RunResult(run, links, new_links, dropped, run.counts)


def record_exact_run(session: Session, *, source: str, dataset: str, counts: dict) -> MatchRun:
    """A run for a source linked only by its own stable key (FPL)."""
    now = datetime.now(UTC)
    run = MatchRun(
        source=source,
        dataset=dataset,
        matcher_version=settings()["matcher_version"],
        settings={"stages": ["exact_key"]},
        counts=counts,
        started_at=now,
        finished_at=now,
    )
    session.add(run)
    session.flush()
    return run
