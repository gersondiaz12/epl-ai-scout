import json
from datetime import date

import httpx
import pytest
from sqlalchemy import func, select

from app.ingest.fpl import (
    FplClient,
    ReconciliationError,
    history_totals,
    load,
    player_name,
    reconcile,
    season_label,
    stats_rows,
)
from app.models import ClubSeason, PlayerSeasonStats
from tests import fpl_payload as fpl

FIXTURES = {f["id"]: f for f in fpl.FIXTURES}
TEAM_CODES = {t["id"]: t["code"] for t in fpl.TEAMS}


def test_season_label():
    assert season_label(date(2026, 8, 21)) == "2026-27"
    assert season_label(date(2099, 8, 1)) == "2099-00"


def test_player_name_prefers_known_name():
    element = {"first_name": "Francisco Evanilson", "second_name": "de Lima Barbosa"}
    assert player_name(element | {"known_name": "Evanilson"}) == "Evanilson"
    assert player_name(element | {"known_name": ""}) == "Francisco Evanilson de Lima Barbosa"
    assert player_name(element) == "Francisco Evanilson de Lima Barbosa"


def test_history_splits_a_mid_season_move_by_club():
    by_team = history_totals(fpl.HISTORIES[102], FIXTURES)
    assert {team: t.minutes for team, t in by_team.items()} == {fpl.COV: 90, fpl.ARS: 90}
    assert all(t.appearances == 1 for t in by_team.values())


def test_appearances_count_only_matches_with_minutes():
    history = [fpl.match(1, True), fpl.match(3, True, minutes=0)]
    (totals,) = history_totals(history, FIXTURES).values()
    assert totals.appearances == 1
    assert totals.minutes == 90


def test_rows_drop_empty_former_clubs_and_keep_the_current_one():
    element = fpl.bootstrap()["elements"][0] | {"team": fpl.COV}
    # Only a 0-minute match for ARS (a former club), no matches yet for COV.
    by_team = history_totals([fpl.match(1, True, minutes=0)], FIXTURES)
    rows = stats_rows(element, by_team, TEAM_CODES)
    assert [(r.team_code, r.is_current_club, r.totals.minutes) for r in rows] == [(9, True, 0)]


def test_reconcile_reports_differences_from_fpl_totals():
    element = fpl.bootstrap()["elements"][0]
    rows = stats_rows(element, history_totals(fpl.HISTORIES[101], FIXTURES), TEAM_CODES)
    assert reconcile(element, rows) == []
    assert reconcile(element | {"minutes": 999}, rows) != []


def test_load_writes_one_row_per_player_club(session_factory):
    with session_factory() as session, session.begin():
        summary = load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)
    assert summary == {
        "clubs": 2,
        "players": 4,
        "stats_rows": 5,
        "players_with_two_clubs": 1,
        "stale_rows_removed": 0,
    }
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ClubSeason)) == 2


def stats_ids(session_factory) -> dict[tuple[int, int], int]:
    with session_factory() as session:
        rows = session.scalars(select(PlayerSeasonStats)).all()
        return {(r.player_id, r.club_id): r.id for r in rows}


def test_rerun_upserts_in_place_and_keeps_row_ids(session_factory):
    with session_factory() as session, session.begin():
        load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)
    first = stats_ids(session_factory)

    # Second run with an extra match for the striker: same rows, updated totals.
    histories = {**fpl.HISTORIES, 101: [*fpl.HISTORIES[101], fpl.match(4, False, goals=1)]}
    bootstrap = fpl.bootstrap()
    striker = bootstrap["elements"][0]
    striker.update(minutes=360, goals_scored=4, expected_goals="2.00")
    with session_factory() as session, session.begin():
        load(session, bootstrap, fpl.FIXTURES, histories)

    assert stats_ids(session_factory) == first
    with session_factory() as session:
        row = session.scalar(select(PlayerSeasonStats).where(PlayerSeasonStats.minutes == 360))
        assert (row.goals, row.appearances) == (4, 4)


def test_rerun_removes_rows_fpl_no_longer_reports(session_factory):
    with session_factory() as session, session.begin():
        load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)
    bootstrap = fpl.bootstrap()
    bootstrap["elements"] = [e for e in bootstrap["elements"] if e["web_name"] != "Keeper"]
    with session_factory() as session, session.begin():
        summary = load(session, bootstrap, fpl.FIXTURES, fpl.HISTORIES)
    assert summary["stale_rows_removed"] == 1
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerSeasonStats)) == 4


def test_raw_response_is_cached_before_parsing(tmp_path):
    body = b'{"elements": [], "note": "caf\xc3\xa9"}'
    client = FplClient(tmp_path)
    client.http = httpx.Client(
        base_url="https://fpl.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body)),
    )
    assert client.get("/bootstrap-static/")["note"] == "café"
    assert (tmp_path / "bootstrap-static.json").read_bytes() == body  # byte-for-byte

    # A body that isn't valid JSON is still saved, then fails to parse.
    client.http = httpx.Client(
        base_url="https://fpl.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"<html>")),
    )
    with pytest.raises(json.JSONDecodeError):
        client.get("/fixtures/")
    assert (tmp_path / "fixtures.json").read_bytes() == b"<html>"
    assert not list(tmp_path.glob("*.part"))


def test_cached_response_is_reused_without_a_request(tmp_path):
    (tmp_path / "fixtures.json").write_bytes(b"[1, 2]")
    client = FplClient(tmp_path)
    client.http = httpx.Client(
        base_url="https://fpl.test", transport=httpx.MockTransport(lambda _: pytest.fail("fetched"))
    )
    assert client.get("/fixtures/") == [1, 2]


def test_load_rolls_back_when_totals_do_not_reconcile(session_factory):
    bootstrap = fpl.bootstrap()
    bootstrap["elements"][0]["goals_scored"] = 99
    with pytest.raises(ReconciliationError), session_factory() as session, session.begin():
        load(session, bootstrap, fpl.FIXTURES, fpl.HISTORIES)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerSeasonStats)) == 0
