from datetime import date

import pytest
from sqlalchemy import func, select

from app.ingest.fpl import (
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
    assert summary == {"clubs": 2, "players": 4, "stats_rows": 5, "players_with_two_clubs": 1}
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ClubSeason)) == 2


def test_load_is_idempotent(session_factory):
    for _ in range(2):
        with session_factory() as session, session.begin():
            load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerSeasonStats)) == 5


def test_load_rolls_back_when_totals_do_not_reconcile(session_factory):
    bootstrap = fpl.bootstrap()
    bootstrap["elements"][0]["goals_scored"] = 99
    with pytest.raises(ReconciliationError), session_factory() as session, session.begin():
        load(session, bootstrap, fpl.FIXTURES, fpl.HISTORIES)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerSeasonStats)) == 0
