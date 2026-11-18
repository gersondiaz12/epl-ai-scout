import json
from datetime import date

import httpx
import pytest
from sqlalchemy import func, select

from app.ingest.fpl import load
from app.ingest.transfermarkt import (
    Ours,
    TmPlayer,
    download,
    load_transfermarkt,
    match_players,
    name_words,
    parse_date,
    similar_words,
    snapshot_version,
)
from app.models import Player, PlayerContract, PlayerMarketValue, PlayerSourceId, SourceSnapshot
from tests import fpl_payload as fpl
from tests import transfermarkt_payload as tmp

# ---------- Pure helpers ----------


def test_parse_date():
    assert parse_date("1998-12-17 00:00:00") == date(1998, 12, 17)
    assert parse_date("2027-06-30") == date(2027, 6, 30)
    assert parse_date("") is None and parse_date(None) is None
    with pytest.raises(ValueError):
        parse_date("30/06/2027")


def test_name_words_ignore_accents_and_short_particles():
    assert name_words("Martin Ødegaard", "Ødegaard") == {"martin", "odegaard"}
    assert "magalhaes" in name_words("Gabriel dos Santos Magalhães")
    assert "da" not in name_words("Joao da Silva")


def test_similar_words():
    assert similar_words({"yarmoliuk"}, {"yarmolyuk"})
    assert similar_words({"savio"}, {"savinho"})
    assert not similar_words({"kitching"}, {"kreida"})
    assert not similar_words({"ali"}, {"aly"})  # under 4 letters never counts


def test_snapshot_version_is_stable_and_order_free():
    a = {"players": {"sha256": "aa"}, "player_valuations": {"sha256": "bb"}}
    b = {"player_valuations": {"sha256": "bb"}, "players": {"sha256": "aa"}}
    assert snapshot_version(a) == snapshot_version(b)
    assert snapshot_version(a) != snapshot_version({**a, "players": {"sha256": "cc"}})


# ---------- Matching ----------


def tm(tid, name, dob, season=2025):
    first, _, last = name.partition(" ")
    return TmPlayer(tid, name, first, last, dob, season, "GB1", "Club", None)


D1, D2 = date(2000, 1, 1), date(2001, 2, 2)


def test_match_rules():
    ours = [
        Ours(1, "Martin Odegaard", "Odegaard", D1),  # exact word
        Ours(2, "Yehor Yarmoliuk", "Yarmoliuk", D2),  # spelling variant only
        Ours(3, "Liam Kitching", "Kitching", date(1999, 9, 25)),  # date shared with someone else
        Ours(4, "Nobody Here", "Here", date(1990, 1, 1)),  # no one born that day
        Ours(5, "Keeper Name", "Name", None),  # name only
        Ours(6, "Ghost Player", "Ghost", None),  # no birth date, no name match
    ]
    candidates = [
        tm("a", "Martin Ødegaard", D1),
        tm("b", "Someone Else", D1),
        tm("c", "Yegor Yarmolyuk", D2),
        tm("d", "Keeper Name", date(1995, 5, 5)),
        tm("e", "Vladislav Kreida", date(1999, 9, 25)),
    ]
    m = match_players(ours, candidates)
    assert m.links == {1: "a", 2: "c", 5: "d"}
    assert dict(m.methods) == {
        "birth_date_and_name": 1,
        "birth_date_and_similar_name": 1,
        "name_only": 1,
    }
    assert {r: len(v) for r, v in m.unlinked.items() if v} == {
        "not_in_dataset": 1,
        "no_birth_date_match": 1,
        "no_birth_date": 1,
    }


def test_match_refuses_ties_and_shared_targets():
    ours = [Ours(1, "Alex Smith", "Smith", D1)]
    m = match_players(ours, [tm("a", "Alex Brown", D1), tm("b", "Alex Green", D1)])
    assert m.links == {} and len(m.unlinked["ambiguous"]) == 1
    # One Transfermarkt player claimed by two of ours links neither.
    twins = [Ours(1, "Chris Wood", "Wood", D1), Ours(2, "Chris Wood", "Wood", D1)]
    m = match_players(twins, [tm("a", "Chris Wood", D1)])
    assert m.links == {} and len(m.unlinked["same_transfermarkt_player"]) == 2


def test_name_only_requires_a_recently_active_player():
    ours = [Ours(1, "Old Legend", "Legend", None)]
    m = match_players(ours, [tm("a", "Old Legend", D1, season=2010), tm("x", "X Y", D2)])
    assert m.links == {} and len(m.unlinked["no_birth_date"]) == 1


# ---------- Loading ----------


@pytest.fixture
def ours(session_factory):
    with session_factory() as session, session.begin():
        load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)
    with session_factory() as session:
        return {p.display_name: p.id for p in session.scalars(select(Player))}


def run(session_factory, folder):
    with session_factory() as session, session.begin():
        return load_transfermarkt(session, folder)


def test_load_links_players_and_reports_everything_not_loaded(session_factory, ours, tmp_path):
    summary = run(session_factory, tmp.write_snapshot(tmp_path / "snap"))
    summary.pop("snapshot_version")
    assert summary == {
        "upstream_commit": "e44f186d6f06",
        "data_through": "2026-06-12",
        "our_players": 4,
        "linked": 3,
        "linked_new": 3,
        "link_methods": {"birth_date_and_name": 2, "name_only": 1},
        "unlinked": {"not_in_dataset": 1},  # Forward
        "unreadable_players": 0,
        "unreadable_valuations": 1,
        "valuations_for_our_players": 3,
        "valuations_written": 3,
        "valuations_other_players": 1,
        "linked_without_valuations": 1,  # Keeper
        "contracts_for_our_players": 2,
        "contracts_written": 2,
        "linked_without_contract_date": 1,  # Mover
        "tm_pl_players_not_ours": 1,  # Other Squad (Old Legend retired long ago)
    }
    with session_factory() as session:
        links = {
            s.player_id: s.external_id
            for s in session.scalars(
                select(PlayerSourceId).where(PlayerSourceId.source == "transfermarkt")
            )
        }
        assert links == {ours["Striker"]: "101", ours["Mover"]: "102", ours["Keeper"]: "103"}
        values = session.scalars(
            select(PlayerMarketValue).order_by(PlayerMarketValue.valued_on)
        ).all()
        assert [(v.player_id, v.valued_on, v.value_eur, v.competition_id) for v in values] == [
            (ours["Striker"], date(2024, 6, 1), 50_000_000, "PO1"),
            (ours["Mover"], date(2025, 6, 12), 8_000_000, "GB1"),
            (ours["Striker"], date(2025, 12, 1), 60_000_000, "GB1"),
        ]
        contracts = {c.player_id: c.expires_on for c in session.scalars(select(PlayerContract))}
        assert contracts == {
            ours["Striker"]: date(2028, 6, 30),
            ours["Keeper"]: date(2027, 6, 30),
        }


def test_snapshot_version_is_recorded_and_cited(session_factory, ours, tmp_path):
    folder = tmp.write_snapshot(tmp_path / "snap")
    run(session_factory, folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    with session_factory() as session:
        (snap,) = session.scalars(select(SourceSnapshot)).all()
        assert snap.version == manifest["version"]
        assert snap.upstream_commit == manifest["upstream_commit"]
        assert snap.data_through == date(2026, 6, 12)
        assert snap.files["players"]["sha256"] == manifest["files"]["players"]["sha256"]
        assert {v.snapshot_id for v in session.scalars(select(PlayerMarketValue))} == {snap.id}
        assert {c.snapshot_id for c in session.scalars(select(PlayerContract))} == {snap.id}


def market_rows(session_factory):
    with session_factory() as session:
        return [
            (v.id, v.value_eur, v.ingested_at)
            for v in session.scalars(select(PlayerMarketValue).order_by(PlayerMarketValue.id))
        ]


def test_rerunning_the_same_snapshot_changes_nothing(session_factory, ours, tmp_path):
    folder = tmp.write_snapshot(tmp_path / "snap")
    run(session_factory, folder)
    before = market_rows(session_factory)
    summary = run(session_factory, folder)
    assert (summary["valuations_written"], summary["contracts_written"]) == (0, 0)
    assert summary["linked_new"] == 0 and summary["linked"] == 3
    assert market_rows(session_factory) == before  # not even ingested_at moves
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SourceSnapshot)) == 1


def test_a_new_snapshot_updates_changed_values_in_place(session_factory, ours, tmp_path):
    run(session_factory, tmp.write_snapshot(tmp_path / "v1"))
    corrected = [dict(v) for v in tmp.VALUATIONS]
    corrected[1]["market_value_in_eur"] = "65000000"  # upstream correction
    summary = run(
        session_factory, tmp.write_snapshot(tmp_path / "v2", tmp.files(valuations=corrected))
    )
    assert summary["valuations_written"] == 1
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SourceSnapshot)) == 2
        row = session.scalar(
            select(PlayerMarketValue).where(PlayerMarketValue.valued_on == date(2025, 12, 1))
        )
        assert row.value_eur == 65_000_000
        assert session.scalar(select(func.count()).select_from(PlayerMarketValue)) == 3


def test_existing_links_win(session_factory, ours, tmp_path):
    with session_factory() as session, session.begin():
        # Checked by hand: the forward is Transfermarkt player 104 after all.
        session.add(
            PlayerSourceId(player_id=ours["Forward"], source="transfermarkt", external_id="104")
        )
    summary = run(session_factory, tmp.write_snapshot(tmp_path / "snap"))
    assert summary["linked"] == 4 and summary["linked_new"] == 3
    assert "not_in_dataset" not in summary["unlinked"]


# ---------- Download (mock transport, never the live source) ----------


def test_download_caches_untouched_files_with_a_manifest(tmp_path):
    blobs = tmp.files()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"sha": "c0ffee" * 6 + "abcd"})
        name = request.url.path.rsplit("/", 1)[-1].removesuffix(".csv.gz")
        headers = {"etag": f'"{name}-1"', "last-modified": "Sat, 05 Sep 2026 09:12:22 GMT"}
        body = b"" if request.method == "HEAD" else blobs[name]
        return httpx.Response(200, headers=headers, content=body)

    transport = httpx.MockTransport(handler)
    folder = download(tmp_path, transport=transport)
    assert folder.name == "2026-09-05"
    for name, blob in blobs.items():
        assert (folder / f"{name}.csv.gz").read_bytes() == blob
    assert not list(folder.glob("*.part"))
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["version"] == snapshot_version(manifest["files"])
    assert manifest["license"] == "CC0-1.0"
    assert manifest["upstream_commit"].startswith("c0ffee")

    # Same ETags: reused without downloading again.
    calls.clear()
    assert download(tmp_path, transport=transport) == folder
    assert set(calls) == {"HEAD"}
