import json
from datetime import date

import httpx
import pytest
from sqlalchemy import func, select

from app.ingest.fpl import load
from app.ingest.transfermarkt import (
    download,
    load_transfermarkt,
    parse_date,
    snapshot_version,
)
from app.models import (
    Club,
    ClubSourceId,
    MatchRun,
    Player,
    PlayerContract,
    PlayerMarketValue,
    PlayerSourceId,
    SourceSnapshot,
    UnmatchedRecord,
)
from tests import fpl_payload as fpl
from tests import transfermarkt_payload as tmp

# ---------- Pure helpers ----------


def test_parse_date():
    assert parse_date("1998-12-17 00:00:00") == date(1998, 12, 17)
    assert parse_date("2027-06-30") == date(2027, 6, 30)
    assert parse_date("") is None and parse_date(None) is None
    with pytest.raises(ValueError):
        parse_date("30/06/2027")


def test_snapshot_version_is_stable_and_order_free():
    a = {"players": {"sha256": "aa"}, "player_valuations": {"sha256": "bb"}}
    b = {"player_valuations": {"sha256": "bb"}, "players": {"sha256": "aa"}}
    assert snapshot_version(a) == snapshot_version(b)
    assert snapshot_version(a) != snapshot_version({**a, "players": {"sha256": "cc"}})


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
        "linked": 2,
        "linked_new": 2,
        "link_methods": {"r1_same_words": 2},
        # Keeper has no birth date and no club evidence yet; Forward shares a
        # birth date only with someone of another name.
        "unlinked": {"no_birth_date": 1, "no_name_match": 1},
        "linked_missing_from_snapshot": 0,
        "unreadable_players": 0,
        "unreadable_valuations": 1,
        "valuations_for_our_players": 3,
        "valuations_written": 3,
        "valuations_kept_from_live_api": 0,
        "valuations_other_players": 1,
        "linked_without_valuations": 0,
        "contracts_for_our_players": 1,
        "contracts_written": 1,
        "linked_without_contract_date": 1,  # Mover
        "tm_pl_players_not_ours": 2,  # Keeper Test, Other Squad (Old Legend retired long ago)
    }
    with session_factory() as session:
        links = {
            s.player_id: s.external_id
            for s in session.scalars(
                select(PlayerSourceId).where(PlayerSourceId.source == "transfermarkt")
            )
        }
        assert links == {ours["Striker"]: "101", ours["Mover"]: "102"}
        values = session.scalars(
            select(PlayerMarketValue).order_by(PlayerMarketValue.valued_on)
        ).all()
        assert [(v.player_id, v.valued_on, v.value_eur, v.competition_id) for v in values] == [
            (ours["Striker"], date(2024, 6, 1), 50_000_000, "PO1"),
            (ours["Mover"], date(2025, 6, 12), 8_000_000, "GB1"),
            (ours["Striker"], date(2025, 12, 1), 60_000_000, "GB1"),
        ]
        contracts = {c.player_id: c.expires_on for c in session.scalars(select(PlayerContract))}
        assert contracts == {ours["Striker"]: date(2028, 6, 30)}
        queued = {(u.side, u.reason, u.name) for u in session.scalars(select(UnmatchedRecord))}
        assert queued == {
            ("our_player", "no_birth_date", "Keeper Test"),
            ("our_player", "no_name_match", "Forward Test"),
        }
        (match_run,) = session.scalars(
            select(MatchRun).where(MatchRun.source == "transfermarkt")
        ).all()
        assert match_run.dataset == "dcaribou/transfermarkt-datasets"
        assert match_run.snapshot_id is not None


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
    assert summary["linked_new"] == 0 and summary["linked"] == 2
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
    assert summary["linked"] == 3 and summary["linked_new"] == 2
    assert "no_name_match" not in summary["unlinked"]


def test_club_evidence_links_a_player_without_a_birth_date(session_factory, ours, tmp_path):
    with session_factory() as session, session.begin():
        coventry = session.scalar(select(Club).where(Club.short_name == "COV"))
        session.add(ClubSourceId(club_id=coventry.id, source="transfermarkt", external_id="990"))
    summary = run(session_factory, tmp.write_snapshot(tmp_path / "snap"))
    assert summary["link_methods"] == {"r1_same_words": 2, "r4_club": 1}
    assert summary["contracts_written"] == 2  # Keeper's contract too


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
