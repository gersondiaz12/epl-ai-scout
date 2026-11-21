"""The live Transfermarkt API job, against a mock transport (never the live API).

Our players come from tests/fpl_payload.py: Striker 2000-01-15, Mover
1998-06-01, Keeper (no birth date), Forward 1995-03-03. Season 2026-27 starts
2026-08-21.
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.ingest.fpl import load
from app.ingest.transfermarkt import load_transfermarkt
from app.ingest.transfermarkt_api import (
    MIN_DELAY,
    UpstreamBlocked,
    check_local,
    fetch,
    load_live,
    season_id,
)
from app.models import Player, PlayerMarketValue, PlayerSourceId, SourceSnapshot
from tests import fpl_payload as fpl
from tests import transfermarkt_payload as bulk

BASE = "http://127.0.0.1:8100"
TODAY = date(2026, 11, 18)


def entry(tid, name, dob, value):
    return {"id": tid, "name": name, "dateOfBirth": dob, "marketValue": value}


COMPETITION = {
    "id": "GB1",
    "name": "Premier League",
    "seasonId": "2026",
    "clubs": [{"id": "11", "name": "Arsenal FC"}, {"id": "990", "name": "Coventry City"}],
}
SQUADS = {
    "11": [
        entry("101", "Striker Test", "2000-01-15", 70_000_000),
        entry("102", "Mover Test", "1998-06-01", 8_000_000),
    ],
    "990": [
        entry("103", "Keeper Test", "1990-01-01", 2_000_000),
        entry("106", "Other Squad", "1999-09-09", 1_000_000),  # not one of ours
    ],
}


def point(day, value, club_id="11", club="Arsenal FC"):
    return {"date": day, "marketValue": value, "clubId": club_id, "clubName": club}


HISTORIES = {
    "101": [
        point("2024-06-01", 50_000_000, "294", "Benfica"),
        point("2025-12-01", 60_000_000),
        point("2026-10-01", 70_000_000),
        point("2026-10-02", None),  # unreadable: no value
    ],
    "102": [point("2025-06-12", 8_000_000)],
    # 103: the API answers 404
}


class FakeApi:
    """Mock transport recording every request; `fail` maps a path to statuses sent first."""

    def __init__(self, fail=None):
        self.calls: list[str] = []
        self.fail = {k: list(v) for k, v in (fail or {}).items()}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(path)
        if self.fail.get(path):
            return httpx.Response(self.fail[path].pop(0), text="blocked")
        if path == "/competitions/GB1/clubs":
            assert request.url.params["season_id"] == "2026"
            return httpx.Response(200, json=COMPETITION)
        if path.startswith("/clubs/"):
            club = path.split("/")[2]
            return httpx.Response(200, json={"id": club, "players": SQUADS[club]})
        if path.startswith("/players/"):
            tid = path.split("/")[2]
            if tid not in HISTORIES:
                return httpx.Response(404, json={"detail": "not found"})
            return httpx.Response(
                200, json={"id": tid, "marketValue": 0, "marketValueHistory": HISTORIES[tid]}
            )
        return httpx.Response(404)


@pytest.fixture
def ours(session_factory):
    with session_factory() as session, session.begin():
        load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)
    with session_factory() as session:
        return {p.display_name: p.id for p in session.scalars(select(Player))}


def run(session_factory, cache: Path, api: FakeApi, sleeps=None, **kw):
    with session_factory() as session:
        fetched = fetch(
            session,
            base_url=BASE,
            cache_root=cache,
            today=TODAY,
            transport=httpx.MockTransport(api),
            sleep=(sleeps.append if sleeps is not None else lambda s: None),
            **kw,
        )
    with session_factory() as session, session.begin():
        return load_live(session, fetched)


def values(session_factory):
    with session_factory() as session:
        return [
            (v.player_id, v.valued_on, v.value_eur, v.club_name, v.competition_id)
            for v in session.scalars(
                select(PlayerMarketValue).order_by(
                    PlayerMarketValue.player_id, PlayerMarketValue.valued_on
                )
            )
        ]


# ---------- Pure helpers ----------


def test_only_a_local_api_is_accepted():
    assert check_local("http://127.0.0.1:8100/") == "http://127.0.0.1:8100"
    assert check_local("http://localhost:8100") == "http://localhost:8100"
    with pytest.raises(ValueError):
        check_local("https://www.transfermarkt.com")


def test_season_id():
    assert season_id("2026-27") == "2026"


def test_no_web_route_imports_the_job():
    """Loading the web app must not load any ingest module."""
    code = (
        "import sys, app.main; print(sorted(m for m in sys.modules if m.startswith('app.ingest')))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "[]"


# ---------- Fetch + load ----------


def test_first_run_links_loads_and_reports_skips(session_factory, ours, tmp_path):
    api = FakeApi()
    summary = run(session_factory, tmp_path, api)
    summary.pop("snapshot_version")
    assert summary == {
        "requests": 6,  # competition, 2 squads, 3 histories
        "reused_from_cache": 0,
        "histories_skipped_value_unchanged": 0,
        "season": "2026",
        "clubs": 2,
        "squad_players": 4,
        "unreadable_squad_entries": 0,
        "linked": 3,
        "linked_new": 3,
        "link_methods": {"birth_date_and_name": 2, "name_only": 1},
        "unlinked": {"no_birth_date_match": 1},  # Forward
        "linked_not_in_pl_squads": 0,
        "squad_players_not_ours": 1,  # Other Squad
        "histories_fetched": 3,
        "valuations_seen": 4,
        "valuations_written": 4,
        "skipped": {"history_not_found": 1, "unreadable_valuation": 1},
        "data_through": "2026-10-01",
    }
    assert "/players/106/market_value" not in api.calls  # not ours: never requested
    s, m = ours["Striker"], ours["Mover"]
    assert values(session_factory) == [
        (s, date(2024, 6, 1), 50_000_000, "Benfica", None),
        (s, date(2025, 12, 1), 60_000_000, "Arsenal FC", None),  # before this season
        (s, date(2026, 10, 1), 70_000_000, "Arsenal FC", "GB1"),
        (m, date(2025, 6, 12), 8_000_000, "Arsenal FC", None),
    ]
    with session_factory() as session:
        snap = session.scalar(select(SourceSnapshot))
        assert snap.dataset == "felipeall/transfermarkt-api"
        assert snap.data_through == date(2026, 10, 1)
        assert "clubs/11_2026.json" in snap.files
        assert {v.snapshot_id for v in session.scalars(select(PlayerMarketValue))} == {snap.id}


def test_every_response_is_cached_untouched(session_factory, ours, tmp_path):
    run(session_factory, tmp_path, FakeApi())
    folder = tmp_path / "2026-11-18"
    names = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    assert names == [
        "clubs/11_2026.json",
        "clubs/990_2026.json",
        "competition_GB1_2026.json",
        "manifest.json",
        "players/101.json",
        "players/102.json",
        "players/103.404",
    ]
    assert not list(folder.rglob("*.part"))


def test_rerun_same_day_makes_no_requests_and_changes_nothing(session_factory, ours, tmp_path):
    run(session_factory, tmp_path, FakeApi())
    with session_factory() as session:
        before = [
            (v.id, v.value_eur, v.ingested_at)
            for v in session.scalars(select(PlayerMarketValue).order_by(PlayerMarketValue.id))
        ]
    api = FakeApi()
    summary = run(session_factory, tmp_path, api)
    assert api.calls == [] and summary["requests"] == 0
    assert summary["valuations_written"] == 0 and summary["linked_new"] == 0
    with session_factory() as session:
        after = [
            (v.id, v.value_eur, v.ingested_at)
            for v in session.scalars(select(PlayerMarketValue).order_by(PlayerMarketValue.id))
        ]
        assert after == before
        assert session.scalar(select(func.count()).select_from(SourceSnapshot)) == 1


def test_after_the_bulk_load_only_changed_values_are_fetched(session_factory, ours, tmp_path):
    with session_factory() as session, session.begin():
        load_transfermarkt(session, bulk.write_snapshot(tmp_path / "bulk"))
    api = FakeApi()
    summary = run(session_factory, tmp_path / "live", api)
    # Mover's squad value equals the 8m we hold: no history request.
    assert "/players/102/market_value" not in api.calls
    assert summary["histories_skipped_value_unchanged"] == 1
    assert summary["linked_new"] == 0
    # Only Striker's new October value is new; the bulk rows keep their league labels.
    assert summary["valuations_written"] == 1
    s = ours["Striker"]
    assert [v for v in values(session_factory) if v[0] == s] == [
        (s, date(2024, 6, 1), 50_000_000, "Benfica", "PO1"),
        (s, date(2025, 12, 1), 60_000_000, "Arsenal FC", "GB1"),
        (s, date(2026, 10, 1), 70_000_000, "Arsenal FC", "GB1"),
    ]


def test_all_histories_fetches_unchanged_players_too(session_factory, ours, tmp_path):
    with session_factory() as session, session.begin():
        load_transfermarkt(session, bulk.write_snapshot(tmp_path / "bulk"))
    api = FakeApi()
    run(session_factory, tmp_path / "live", api, all_histories=True)
    assert "/players/102/market_value" in api.calls


def test_existing_link_wins(session_factory, ours, tmp_path):
    with session_factory() as session, session.begin():
        # Checked by hand: Forward is squad player 106 after all.
        session.add(
            PlayerSourceId(player_id=ours["Forward"], source="transfermarkt", external_id="106")
        )
    summary = run(session_factory, tmp_path, FakeApi())
    assert summary["linked"] == 4 and summary["squad_players_not_ours"] == 0
    assert "no_birth_date_match" not in summary["unlinked"]


# ---------- Throttling and failures ----------


def test_requests_are_spaced_at_least_the_delay(session_factory, ours, tmp_path):
    sleeps: list[float] = []
    run(session_factory, tmp_path, FakeApi(), sleeps=sleeps, delay=5)
    assert len(sleeps) == 5  # between 6 requests
    assert all(4.5 < s <= 5 for s in sleeps)


def test_delay_never_goes_below_the_floor(session_factory, ours, tmp_path):
    sleeps: list[float] = []
    run(session_factory, tmp_path, FakeApi(), sleeps=sleeps, delay=0)
    assert sleeps and all(MIN_DELAY - 0.5 < s <= MIN_DELAY for s in sleeps)


def test_backs_off_on_429_then_succeeds(session_factory, ours, tmp_path):
    sleeps: list[float] = []
    api = FakeApi(fail={"/clubs/11/players": [429, 503]})
    summary = run(session_factory, tmp_path, api, sleeps=sleeps)
    assert 30.0 in sleeps and 60.0 in sleeps
    assert summary["valuations_written"] == 4


def test_a_blocked_upstream_stops_the_run_before_loading(session_factory, ours, tmp_path):
    api = FakeApi(fail={"/clubs/990/players": [503] * 10})
    with pytest.raises(UpstreamBlocked):
        run(session_factory, tmp_path, api)
    assert api.calls.count("/clubs/990/players") == 4  # first try + 3 backoffs
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerMarketValue)) == 0
        assert session.scalar(select(func.count()).select_from(SourceSnapshot)) == 0


def test_wrong_season_is_refused(session_factory, ours, tmp_path, monkeypatch):
    monkeypatch.setitem(COMPETITION, "seasonId", "2025")
    with pytest.raises(RuntimeError, match="season 2026"):
        run(session_factory, tmp_path, FakeApi())
