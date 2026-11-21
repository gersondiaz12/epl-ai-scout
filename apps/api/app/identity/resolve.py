"""Operator decisions on player links. Each command applies straight away.

    uv run python -m app.identity.resolve open --source transfermarkt
    uv run python -m app.identity.resolve link --source transfermarkt --external-id 1049914 \\
        --player 60 --reason "checked: same academy player" --by <name>
    uv run python -m app.identity.resolve reject --source transfermarkt --external-id 1049914 \\
        --player 60 --reason "..." --by <name>
    uv run python -m app.identity.resolve no-match --source transfermarkt --player 566 \\
        --reason "academy player, no Transfermarkt profile" --by <name>
    uv run python -m app.identity.resolve undo --decision 42 --reason "..." --by <name>

Decisions are append-only: a new decision for the same record supersedes the
old one, which is kept. Matcher runs only read them, so a decision is never
overwritten. Data loaded through a link that a decision removes is deleted;
data for a new manual link arrives on the source's next ingest run.
"""

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.identity.matcher import apply_decisions, drop_source_rows
from app.models import MatchRun, Player, PlayerMatchDecision, PlayerSourceId, UnmatchedRecord


def open_records(session: Session, source: str) -> list[UnmatchedRecord]:
    """Unmatched records seen in the latest run of each of the source's datasets."""
    latest = (
        select(MatchRun.dataset, func.max(MatchRun.id).label("run_id"))
        .where(MatchRun.source == source)
        .group_by(MatchRun.dataset)
        .subquery()
    )
    return list(
        session.scalars(
            select(UnmatchedRecord)
            .join(
                latest,
                (latest.c.dataset == UnmatchedRecord.dataset)
                & (latest.c.run_id == UnmatchedRecord.last_seen_run_id),
            )
            .where(UnmatchedRecord.source == source)
            .order_by(UnmatchedRecord.dataset, UnmatchedRecord.reason, UnmatchedRecord.name)
        )
    )


def decide(
    session: Session,
    *,
    source: str,
    decision: str,
    reason: str,
    by: str,
    external_id: str | None = None,
    player_id: int | None = None,
) -> PlayerMatchDecision:
    """Record a decision, superseding the active ones it replaces, and apply it."""
    if not reason.strip():
        raise ValueError("a reason is required")
    if player_id is not None and session.get(Player, player_id) is None:
        raise ValueError(f"no player {player_id}")
    new = PlayerMatchDecision(
        source=source,
        external_id=external_id,
        player_id=player_id,
        decision=decision,
        reason=reason.strip(),
        decided_by=by,
    )
    # Which active decisions this one replaces.
    if decision == "reject":
        clash = [
            PlayerMatchDecision.decision == "reject",
            PlayerMatchDecision.external_id == external_id,
            PlayerMatchDecision.player_id == player_id,
        ]
    else:
        either = []
        if external_id is not None:
            either.append(PlayerMatchDecision.external_id == external_id)
        if player_id is not None:
            either.append(PlayerMatchDecision.player_id == player_id)
        clash = [PlayerMatchDecision.decision != "reject", or_(*either)]
    old = list(
        session.scalars(
            select(PlayerMatchDecision).where(
                PlayerMatchDecision.source == source,
                PlayerMatchDecision.superseded_by.is_(None),
                *clash,
            )
        )
    )
    # A link the operator now rejects can't stay a manual link.
    if decision == "reject":
        old += list(
            session.scalars(
                select(PlayerMatchDecision).where(
                    PlayerMatchDecision.source == source,
                    PlayerMatchDecision.superseded_by.is_(None),
                    PlayerMatchDecision.decision == "link",
                    PlayerMatchDecision.external_id == external_id,
                    PlayerMatchDecision.player_id == player_id,
                )
            )
        )
    for d in old:
        d.superseded_by = d.id  # withdrawn first, so the new row never clashes with it
    session.flush()
    session.add(new)
    session.flush()
    for d in old:
        d.superseded_by = new.id
    session.flush()
    apply_decisions(session, source, datetime.now(UTC))
    return new


def undo(session: Session, decision_id: int, *, reason: str, by: str) -> PlayerMatchDecision:
    """Withdraw a decision. Its record goes back to the automatic stages on the next run.

    Stored as a superseding row so the history shows who withdrew it and why;
    the withdrawing row itself is superseded at once, so nothing stays active.
    """
    d = session.get(PlayerMatchDecision, decision_id)
    if d is None or d.superseded_by is not None:
        raise ValueError(f"decision {decision_id} is not active")
    d.superseded_by = d.id  # withdrawn first, so the note never clashes with it
    session.flush()
    note = PlayerMatchDecision(
        source=d.source,
        external_id=d.external_id,
        player_id=d.player_id,
        decision=d.decision,
        reason=f"undo #{d.id}: {reason.strip()}",
        decided_by=by,
    )
    session.add(note)
    session.flush()
    note.superseded_by = note.id  # a withdrawal is never itself active
    d.superseded_by = note.id
    session.flush()
    # A withdrawn manual link is removed with its data; the next run applies the rules again.
    if d.decision == "link":
        row = session.scalar(
            select(PlayerSourceId).where(
                PlayerSourceId.source == d.source,
                PlayerSourceId.player_id == d.player_id,
                PlayerSourceId.external_id == d.external_id,
            )
        )
        if row is not None:
            session.delete(row)
            session.flush()
            drop_source_rows(session, d.source, {d.player_id})
    return note


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    o = sub.add_parser("open", help="list open unmatched records with their candidates")
    o.add_argument("--source", required=True)
    for name in ("link", "reject", "no-match"):
        p = sub.add_parser(name)
        p.add_argument("--source", required=True)
        p.add_argument("--external-id")
        p.add_argument("--player", type=int)
        p.add_argument("--reason", required=True)
        p.add_argument("--by", required=True)
    u = sub.add_parser("undo")
    u.add_argument("--decision", type=int, required=True)
    u.add_argument("--reason", required=True)
    u.add_argument("--by", required=True)
    args = parser.parse_args()

    with SessionLocal() as session, session.begin():
        if args.command == "open":
            for r in open_records(session, args.source):
                ident = r.external_id or f"player {r.player_id}"
                print(f"[{r.dataset}] {r.side} {ident} {r.name} ({r.birth_date}) {r.reason}")
                for c in r.candidates:
                    print("    ", json.dumps(c, ensure_ascii=False))
            return
        if args.command == "undo":
            note = undo(session, args.decision, reason=args.reason, by=args.by)
            print(f"withdrew decision {args.decision} (#{note.id})")
            return
        d = decide(
            session,
            source=args.source,
            decision=args.command.replace("-", "_"),
            external_id=args.external_id,
            player_id=args.player,
            reason=args.reason,
            by=args.by,
        )
        print(f"decision #{d.id}: {d.decision} {d.external_id} {d.player_id}")


if __name__ == "__main__":
    main()
