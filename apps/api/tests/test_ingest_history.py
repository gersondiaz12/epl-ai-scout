from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.ingest.fpl import load
from app.ingest.fpl_history import (
    fpl_season_label,
    load_history,
    parse_history,
    parse_value,
    previous_labels,
)
from app.models import PlayerSeasonTotals, Season
from tests import fpl_payload as fpl

SEASONS = ["2025-26", "2024-25", "2023-24"]


@pytest.fixture
def current(session_factory):
    """The daily ingest has run: 2026-27 is current and players are linked."""
    with session_factory() as session, session.begin():
        load(session, fpl.bootstrap(), fpl.FIXTURES, fpl.HISTORIES)


def run(session_factory, summaries=None):
    with session_factory() as session, session.begin():
        return load_history(session, fpl.summaries() if summaries is None else summaries)


def totals(session_factory) -> dict[tuple[str, str], PlayerSeasonTotals]:
    with session_factory() as session:
        rows = session.scalars(select(PlayerSeasonTotals)).all()
        out = {(r.player.display_name, r.season.label): r for r in rows}
        session.expunge_all()
        return out


def test_labels():
    assert fpl_season_label("2024/25") == "2024-25"
    assert previous_labels("2026-27", 3) == SEASONS
    assert previous_labels("2000-01", 1) == ["1999-00"]


@pytest.mark.parametrize(
    ("column", "raw"), [("xg", "abc"), ("xg", "NaN"), ("minutes", None), ("tackles", -1)]
)
def test_parse_value_rejects_bad_numbers(column, raw):
    with pytest.raises(ValueError):
        parse_value(column, raw)


def test_parse_history_counts_every_skip_and_nulls_untracked_fields():
    parsed = parse_history(fpl.summaries(), SEASONS)
    assert parsed.out_of_range == 1  # Striker 2019/20
    assert len(parsed.unparseable) == 1 and "xg='abc'" in parsed.unparseable[0]
    assert len(parsed.rows) == 4  # Striker x2, Mover, unknown code
    # 2024/25: every row had 0 tackles/CBI/recoveries, so FPL didn't track them.
    assert parsed.untracked["2024-25"] == ["cbi", "recoveries", "tackles"]
    striker_2425 = next(r for r in parsed.rows if r.season == "2024-25")
    assert striker_2425.values["tackles"] is None
    assert striker_2425.values["xg"] == Decimal("1.50")  # tracked: kept
    assert striker_2425.values["penalties_saved"] == 0  # long-standing field: real zero


def test_load_links_rows_and_reports_what_it_could_not(session_factory, current):
    summary = run(session_factory)
    assert summary == {
        "seasons": SEASONS,
        "rows_by_season": {"2025-26": 1, "2024-25": 1, "2023-24": 1},
        "linked": 3,
        "unlinked": 1,  # element code 7777
        "unparseable": 1,
        "out_of_range_rows": 1,
        "zero_minute_rows": 1,
        "kept_not_in_source": 0,
        "untracked": {
            "2024-25": ["cbi", "recoveries", "tackles"],
            "2023-24": ["cbi", "recoveries", "starts", "tackles", "xa", "xg", "xg_conceded"],
        },
    }
    rows = totals(session_factory)
    striker = rows[("Striker", "2025-26")]
    assert (striker.minutes, striker.tackles, striker.cbi, striker.xg) == (
        900,
        15,
        30,
        Decimal("1.50"),
    )
    assert rows[("Mover", "2023-24")].minutes == 0


def test_past_seasons_are_created_without_dates_and_not_current(session_factory, current):
    run(session_factory)
    with session_factory() as session:
        seasons = {s.label: s for s in session.scalars(select(Season))}
        assert seasons["2026-27"].is_current
        for label in SEASONS:
            assert (seasons[label].start_date, seasons[label].end_date) == (None, None)
            assert not seasons[label].is_current


def test_rerun_is_idempotent(session_factory, current):
    run(session_factory)
    first = {k: (v.id, v.minutes, v.tackles) for k, v in totals(session_factory).items()}
    summary = run(session_factory)
    assert {k: (v.id, v.minutes, v.tackles) for k, v in totals(session_factory).items()} == first
    assert summary["linked"] == 3
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Season)) == 4


def test_rerun_updates_values_in_place(session_factory, current):
    run(session_factory)
    before = totals(session_factory)[("Striker", "2025-26")].id
    changed = fpl.summaries()
    changed[0]["history_past"][2]["tackles"] = 16  # FPL corrects a figure
    run(session_factory, changed)
    after = totals(session_factory)[("Striker", "2025-26")]
    assert (after.id, after.tackles) == (before, 16)


def test_rows_fpl_stops_listing_are_kept_and_counted(session_factory, current):
    run(session_factory)
    summary = run(session_factory, fpl.summaries()[1:])  # the striker's history is gone
    assert summary["kept_not_in_source"] == 2
    assert ("Striker", "2025-26") in totals(session_factory)


def test_requires_the_current_season(session_factory):
    with pytest.raises(RuntimeError, match="No current season"):
        run(session_factory)
