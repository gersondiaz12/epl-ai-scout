from datetime import date

import pytest

from app.ingest.club_reference import PROMOTED
from app.ingest.fpl import load
from tests import fpl_payload as fpl


@pytest.fixture
def loaded(session_factory, client):
    """Load the synthetic payload, then return {name: player id}."""
    assert 9 in PROMOTED["2026-27"]  # the fixture's COV uses Coventry's real team code
    with session_factory() as session, session.begin():
        load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)
    squads = (
        client.get("/clubs/arsenal").json()["squad"]
        + client.get("/clubs/coventry-city").json()["squad"]
    )
    return {p["name"].split()[0]: p["player_id"] for p in squads}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_current_season(client, loaded):
    assert client.get("/seasons/current").json() == {
        "label": "2026-27",
        "start_date": "2026-08-21",
        "end_date": "2027-05-30",
        "per90_min_minutes": 270,
    }


def test_club_list_summaries(client, loaded):
    clubs = {c["slug"]: c for c in client.get("/clubs").json()}
    assert set(clubs) == {"arsenal", "coventry-city"}
    assert clubs["coventry-city"]["promoted"] is True
    assert clubs["arsenal"]["ground"] == "Emirates Stadium"
    assert clubs["arsenal"]["squad_size"] == 2  # Striker and Mover
    assert clubs["arsenal"]["top_scorer"]["goals"] == 3
    assert clubs["coventry-city"]["top_scorer"] is None  # no goals scored


def test_squad_shows_each_clubs_share_of_a_transfer(client, loaded):
    ars = {p["name"].split()[0]: p for p in client.get("/clubs/arsenal").json()["squad"]}
    cov = {p["name"].split()[0]: p for p in client.get("/clubs/coventry-city").json()["squad"]}
    assert (ars["Mover"]["minutes"], ars["Mover"]["is_current_club"]) == (90, True)
    assert (cov["Mover"]["minutes"], cov["Mover"]["is_current_club"]) == (90, False)
    assert cov["Keeper"]["minutes"] == 0  # in the squad without having played


def test_squad_per90_is_null_under_threshold(client, loaded):
    ars = {p["name"].split()[0]: p for p in client.get("/clubs/arsenal").json()["squad"]}
    assert ars["Mover"]["per90"]["xg"] is None  # 90 minutes at ARS
    assert ars["Striker"]["per90"]["ga"] == pytest.approx(1.0)  # 3 goals in 270 minutes


def test_player_totals_span_both_clubs(client, loaded):
    player = client.get(f"/players/{loaded['Mover']}").json()
    assert player["club"]["slug"] == "arsenal"
    assert player["totals"]["minutes"] == 180
    assert [(c["club"]["slug"], c["is_current_club"]) for c in player["by_club"]] == [
        ("arsenal", True),
        ("coventry-city", False),
    ]


def test_percentiles_compare_only_the_same_position(client, loaded):
    striker = client.get(f"/players/{loaded['Striker']}").json()
    pct = striker["percentiles"]
    # Pool: the two forwards with 270+ minutes. The midfielder is excluded.
    assert pct["pool_size"] == 2
    goals = next(r for r in pct["rows"] if r["key"] == "goals")
    assert goals["percentile"] == pytest.approx(75)  # beats one, ties itself
    assert goals["per90"] == pytest.approx(1.0)


def test_percentiles_null_under_minutes_threshold(client, loaded):
    keeper = client.get(f"/players/{loaded['Keeper']}").json()
    assert keeper["percentiles"]["rows"] is None
    assert keeper["age"] is None  # no birth date in the source


@pytest.mark.parametrize(
    "url", ["/clubs/west-ham-united", "/players/999999", "/clubs?season=1999-00"]
)
def test_unknown_resources_404(client, loaded, url):
    assert client.get(url).status_code == 404


def test_in_form_ranks_by_form_above_the_minutes_threshold(client, loaded):
    body = client.get("/in-form").json()
    assert body["season"] == "2026-27"
    assert body["min_minutes"] == 270
    # Striker (270 mins) and Forward (360) qualify; Mover (180) and Keeper (0) don't.
    assert body["pool_size"] == 2
    assert body["without_form"] == 0
    assert body["form_updated_at"] is not None
    assert [(p["rank"], p["name"], p["form"]) for p in body["players"]] == [
        (1, "Striker Test", 6.5),
        (2, "Forward Test", -0.8),
    ]
    striker = body["players"][0]
    assert striker["club"]["slug"] == "arsenal"
    assert (striker["minutes"], striker["goals"], striker["per90"]["ga"]) == (270, 3, 1.0)


def test_in_form_ties_share_a_rank_and_minutes_order_them(client, session_factory):
    bootstrap = fpl.bootstrap()
    bootstrap["elements"][3]["form"] = "6.5"  # Forward level with Striker
    with session_factory() as session, session.begin():
        load(session, bootstrap, fpl.FIXTURES, fpl.HISTORIES)
    players = client.get("/in-form").json()["players"]
    assert [(p["rank"], p["name"]) for p in players] == [(1, "Forward Test"), (1, "Striker Test")]


def test_in_form_counts_but_does_not_rank_players_without_form(client, session_factory):
    bootstrap = fpl.bootstrap()
    bootstrap["elements"][3]["form"] = None
    with session_factory() as session, session.begin():
        load(session, bootstrap, fpl.FIXTURES, fpl.HISTORIES)
    body = client.get("/in-form").json()
    assert (body["pool_size"], body["without_form"]) == (1, 1)
    assert [p["name"] for p in body["players"]] == ["Striker Test"]


def test_in_form_limit(client, loaded):
    body = client.get("/in-form?limit=1").json()
    assert [p["name"] for p in body["players"]] == ["Striker Test"]
    assert body["pool_size"] == 2  # the pool is still counted in full
    assert client.get("/in-form?limit=0").status_code == 422
    assert client.get("/in-form?season=1999-00").status_code == 404


def test_position_lists_every_player_by_current_position(client, loaded):
    body = client.get("/positions/FWD").json()
    assert (body["season"], body["position"], body["min_minutes"]) == ("2026-27", "FWD", 270)
    # Forward 360 mins, Striker 270: most minutes first.
    assert [(p["name"], p["minutes"]) for p in body["players"]] == [
        ("Forward Test", 360),
        ("Striker Test", 270),
    ]
    assert body["players"][1]["per90"]["ga"] == 1.0


def test_position_includes_players_under_the_threshold_with_null_rates(client, loaded):
    keeper = client.get("/positions/GK").json()["players"]
    assert [(p["name"], p["minutes"]) for p in keeper] == [("Keeper Test", 0)]
    assert set(keeper[0]["per90"].values()) == {None}


def test_position_totals_span_clubs_and_show_the_current_club(client, loaded):
    (mover,) = client.get("/positions/MID").json()["players"]
    assert (mover["club"]["slug"], mover["minutes"], mover["appearances"]) == ("arsenal", 180, 2)


@pytest.mark.parametrize("url", ["/positions/XYZ", "/positions/fwd"])
def test_position_rejects_unknown_groups(client, loaded, url):
    assert client.get(url).status_code == 422


def test_position_unknown_season_404(client, loaded):
    assert client.get("/positions/GK?season=1999-00").status_code == 404


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 17)  # Striker 26, Mover 28, Forward 31, Keeper unknown


@pytest.fixture
def search(client, session_factory, monkeypatch):
    """Load the payload with an accented name, and pin today's date for ages."""
    from app.routers import search as search_router

    monkeypatch.setattr(search_router, "date", FixedDate)
    bootstrap = fpl.bootstrap()
    striker = bootstrap["elements"][0]
    striker.update(first_name="Martin", second_name="Ødegaard", web_name="Ødegaard")
    with session_factory() as session, session.begin():
        load(session, bootstrap, fpl.FIXTURES, fpl.HISTORIES)
    return lambda params="": client.get(f"/players?{params}")


def names(response):
    return [p["name"] for p in response.json()["players"]]


@pytest.mark.parametrize("q", ["Odegaard", "odegaard", "ØDEGAARD", "martin ode", "Ødegaard"])
def test_search_is_accent_and_case_insensitive(search, q):
    assert names(search(f"q={q}")) == ["Martin Ødegaard"]


def test_search_without_query_lists_everyone_by_minutes(search):
    body = search().json()
    assert body["total"] == 4
    assert names(search()) == ["Forward Test", "Martin Ødegaard", "Mover Test", "Keeper Test"]


def test_search_filters_by_position(search):
    assert names(search("position=FWD")) == ["Forward Test", "Martin Ødegaard"]
    assert names(search("q=test&position=GK")) == ["Keeper Test"]


def test_search_age_range_is_inclusive_and_counts_unknown_ages(search):
    body = search("min_age=26&max_age=28").json()
    assert [(p["name"], p["age"]) for p in body["players"]] == [
        ("Martin Ødegaard", 26),
        ("Mover Test", 28),
    ]
    assert body["unknown_age_excluded"] == 1  # Keeper has no birth date
    assert search().json()["unknown_age_excluded"] == 0  # no age filter, nobody excluded


def test_search_combines_filters_and_reports_the_full_total(search):
    body = search("q=test&position=FWD&max_age=40&limit=1").json()
    assert body["total"] == 1
    assert names(search("limit=2")) == ["Forward Test", "Martin Ødegaard"]
    assert search("limit=2").json()["total"] == 4


def test_search_rows_carry_totals_across_clubs(search):
    (mover,) = search("q=mover").json()["players"]
    assert (mover["club"]["slug"], mover["minutes"], mover["appearances"]) == ("arsenal", 180, 2)


@pytest.mark.parametrize(
    "params", ["min_age=30&max_age=20", "min_age=10", "max_age=60", "position=XX"]
)
def test_search_rejects_bad_filters(search, params):
    assert search(params).status_code == 422
