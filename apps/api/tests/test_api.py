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
