"""The matcher against the test database: stored links, manual decisions, the
unmatched queue and match-rate counts.

Our players come from tests/fpl_payload.py: Striker 2000-01-15, Mover
1998-06-01, Keeper (no birth date), Forward 1995-03-03.
"""

from datetime import date

import pytest
from sqlalchemy import func, select

from app.identity.matcher import resolve
from app.identity.report import report
from app.identity.resolve import decide, open_records, undo
from app.identity.stages import Person
from app.ingest.fpl import load
from app.models import (
    MatchRun,
    Player,
    PlayerMarketValue,
    PlayerMatchDecision,
    PlayerSourceId,
    SourceSnapshot,
)
from tests import fpl_payload as fpl

SOURCE, DATASET = "transfermarkt", "test-dataset"

RECORDS = [
    Person("101", ("Striker Test",), date(2000, 1, 15)),
    Person("102", ("Mover Test",), date(1998, 6, 1)),
    Person("104", ("Someone Else",), date(1995, 3, 3)),  # Forward's birth date only
    Person("106", ("Other Squad",), date(1999, 9, 9)),  # not one of ours
]


@pytest.fixture
def ours(session_factory):
    with session_factory() as session, session.begin():
        load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)
    with session_factory() as session:
        return {p.display_name: p.id for p in session.scalars(select(Player))}


def run(session_factory, records=RECORDS):
    with session_factory() as session, session.begin():
        return resolve(
            session, source=SOURCE, dataset=DATASET, records=records, in_scope=lambda r: True
        ).counts


def links(session_factory):
    with session_factory() as session:
        return {
            s.player_id: (s.external_id, s.method)
            for s in session.scalars(select(PlayerSourceId).where(PlayerSourceId.source == SOURCE))
        }


def queue(session_factory):
    with session_factory() as session:
        return {(r.side, r.reason, r.name) for r in open_records(session, SOURCE)}


def decision(session_factory, **kw):
    with session_factory() as session, session.begin():
        return decide(session, source=SOURCE, by="tester", **kw).id


def test_first_run_links_queues_and_counts(session_factory, ours):
    counts = run(session_factory)
    assert links(session_factory) == {
        ours["Striker"]: ("101", "r1_same_words"),
        ours["Mover"]: ("102", "r1_same_words"),
    }
    assert queue(session_factory) == {
        ("our_player", "no_birth_date", "Keeper Test"),
        ("our_player", "no_name_match", "Forward Test"),
        ("source_record", "source_record_not_ours", "Someone Else"),
        ("source_record", "source_record_not_ours", "Other Squad"),
    }
    assert counts["linked"] == 2 and counts["records_in_scope"] == 4
    assert counts["unmatched_our_players"] == {"no_birth_date": 1, "no_name_match": 1}


def test_rerun_is_idempotent(session_factory, ours):
    run(session_factory)
    before_links, before_queue = links(session_factory), queue(session_factory)
    counts = run(session_factory)
    assert counts["linked_new"] == 0
    assert links(session_factory) == before_links
    assert queue(session_factory) == before_queue
    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(MatchRun).where(MatchRun.source == SOURCE)
            )
            == 2
        )


def test_manual_link_is_never_overwritten(session_factory, ours):
    run(session_factory)
    # Checked by hand: Forward is Transfermarkt 104 after all.
    decision(
        session_factory,
        decision="link",
        external_id="104",
        player_id=ours["Forward"],
        reason="same player, name changed",
    )
    assert links(session_factory)[ours["Forward"]] == ("104", "manual")
    for _ in range(2):
        run(session_factory)
        assert links(session_factory)[ours["Forward"]] == ("104", "manual")
    assert ("our_player", "no_name_match", "Forward Test") not in queue(session_factory)


def test_manual_link_moves_an_automatic_one_and_clears_its_data(session_factory, ours):
    run(session_factory)
    with session_factory() as session, session.begin():
        snap = SourceSnapshot(
            source=SOURCE, dataset=DATASET, version="v", files={}, retrieved_at=date(2026, 1, 1)
        )
        session.add(snap)
        session.flush()
        session.add(
            PlayerMarketValue(
                player_id=ours["Striker"],
                source=SOURCE,
                valued_on=date(2026, 6, 1),
                value_eur=1,
                snapshot_id=snap.id,
            )
        )
    # 101 is really the Mover's record: the Striker's automatic link goes, with its data.
    decision(
        session_factory, decision="link", external_id="101", player_id=ours["Mover"], reason="x"
    )
    assert links(session_factory)[ours["Mover"]] == ("101", "manual")
    assert ours["Striker"] not in links(session_factory)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerMarketValue)) == 0
    run(session_factory)
    # The Striker's record is taken now; the rules can't hand it back.
    assert ours["Striker"] not in links(session_factory)
    assert ("our_player", "target_already_linked", "Striker Test") in queue(session_factory)


def test_reject_removes_the_link_and_it_never_comes_back(session_factory, ours):
    run(session_factory)
    decision(
        session_factory,
        decision="reject",
        external_id="101",
        player_id=ours["Striker"],
        reason="different person",
    )
    assert ours["Striker"] not in links(session_factory)
    for _ in range(2):
        run(session_factory)
        assert ours["Striker"] not in links(session_factory)
    assert ("our_player", "rejected_by_operator", "Striker Test") in queue(session_factory)


def test_no_match_closes_the_record(session_factory, ours):
    decision(
        session_factory,
        decision="no_match",
        player_id=ours["Keeper"],
        reason="academy player, no Transfermarkt profile",
    )
    decision(session_factory, decision="no_match", external_id="106", reason="youth player")
    run(session_factory)
    names = {name for _, _, name in queue(session_factory)}
    assert "Keeper Test" not in names and "Other Squad" not in names


def test_undo_hands_the_record_back_to_the_rules(session_factory, ours):
    run(session_factory)
    d = decision(
        session_factory, decision="link", external_id="104", player_id=ours["Forward"], reason="x"
    )
    with session_factory() as session, session.begin():
        undo(session, d, reason="checked again: wrong", by="tester")
    run(session_factory)
    assert ours["Forward"] not in links(session_factory)
    assert ("our_player", "no_name_match", "Forward Test") in queue(session_factory)
    with session_factory() as session:
        rows = session.scalars(select(PlayerMatchDecision).order_by(PlayerMatchDecision.id)).all()
        assert len(rows) == 2 and all(r.superseded_by is not None for r in rows)  # history kept


def test_a_new_decision_supersedes_the_old_one(session_factory, ours):
    first = decision(
        session_factory, decision="link", external_id="104", player_id=ours["Forward"], reason="a"
    )
    decision(session_factory, decision="no_match", player_id=ours["Forward"], reason="b")
    with session_factory() as session:
        assert session.get(PlayerMatchDecision, first).superseded_by is not None
    assert ours["Forward"] not in links(session_factory)


def test_a_decision_needs_a_reason(session_factory, ours):
    with pytest.raises(ValueError, match="reason"):
        decision(session_factory, decision="no_match", player_id=ours["Keeper"], reason=" ")


def test_legacy_links_are_relabelled_never_changed(session_factory, ours):
    with session_factory() as session, session.begin():
        session.add(PlayerSourceId(player_id=ours["Striker"], source=SOURCE, external_id="101"))
        # No rule supports this one; it is kept as it is.
        session.add(PlayerSourceId(player_id=ours["Forward"], source=SOURCE, external_id="104"))
    counts = run(session_factory)
    assert links(session_factory)[ours["Striker"]] == ("101", "r1_same_words")
    assert links(session_factory)[ours["Forward"]] == ("104", "legacy")
    assert counts["legacy_relabelled"] == 1 and counts["legacy_without_rule_support"] == 1


def test_a_conflicting_stored_link_is_kept_and_queued(session_factory, ours):
    with session_factory() as session, session.begin():
        session.add(
            PlayerSourceId(
                player_id=ours["Striker"], source=SOURCE, external_id="106", method="r1_same_words"
            )
        )
    counts = run(session_factory)
    assert links(session_factory)[ours["Striker"]] == ("106", "r1_same_words")
    assert counts["conflicts_with_existing_link"] == 1
    assert ("our_player", "conflict_with_existing_link", "Striker Test") in queue(session_factory)


def test_resolved_records_leave_the_open_queue(session_factory, ours):
    run(session_factory)
    assert ("our_player", "no_name_match", "Forward Test") in queue(session_factory)
    fixed = [*RECORDS[:2], Person("104", ("Forward Test",), date(1995, 3, 3)), RECORDS[3]]
    run(session_factory, fixed)
    assert ("our_player", "no_name_match", "Forward Test") not in queue(session_factory)


def test_report_gives_match_rate_per_source(session_factory, ours):
    run(session_factory)
    with session_factory() as session:
        r = report(session)
    tm = next(d for d in r["datasets"] if d["dataset"] == DATASET)
    assert (tm["linked"], tm["our_players"], tm["records_in_scope"]) == (2, 4, 4)
    assert r["links"][SOURCE]["players_linked"] == "2/4 (50.0%)"
    assert r["links"][SOURCE]["by_method"] == {"r1_same_words": 2}
    assert r["links"]["fpl"]["by_method"] == {"exact_key": 4}
    assert r["links"][SOURCE]["open_unmatched"] == {
        "no_birth_date": 1,
        "no_name_match": 1,
        "source_record_not_ours": 2,
    }
