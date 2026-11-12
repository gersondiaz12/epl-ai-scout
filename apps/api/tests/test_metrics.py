from decimal import Decimal

import pytest

from app.metrics import PER90_MIN_MINUTES, Totals, per90, percentile, sum_totals


def test_per90_is_null_below_minutes_threshold():
    assert per90(3, PER90_MIN_MINUTES - 1) is None
    assert per90(3, PER90_MIN_MINUTES) == pytest.approx(1.0)
    assert per90(Decimal("4.50"), 900) == pytest.approx(0.45)


def test_percentile_ties_share_the_mid_rank():
    assert percentile(0.0, [0.0, 0.0, 0.0, 0.0]) == 50
    assert percentile(2.0, [1.0, 2.0, 3.0, 4.0]) == pytest.approx(37.5)


def test_percentile_extremes():
    pool = [1.0, 2.0, 3.0, 4.0]
    assert percentile(4.0, pool) == pytest.approx(87.5)
    assert percentile(1.0, pool) == pytest.approx(12.5)


def test_percentile_lower_is_better_inverts_the_ranking():
    pool = [0.5, 1.0, 1.5, 2.0]
    assert percentile(0.5, pool, higher_is_better=False) == pytest.approx(87.5)
    assert percentile(2.0, pool, higher_is_better=False) == pytest.approx(12.5)


def test_percentile_rejects_empty_pool():
    with pytest.raises(ValueError):
        percentile(1.0, [])


def test_sum_totals_adds_every_field():
    a = Totals(appearances=1, minutes=90, goals=1, xg=Decimal("0.40"), saves=2)
    b = Totals(
        appearances=2, minutes=120, assists=1, xa=Decimal("0.30"), xg_conceded=Decimal("1.10")
    )
    assert sum_totals([a, b]) == Totals(
        appearances=3,
        minutes=210,
        goals=1,
        assists=1,
        xg=Decimal("0.40"),
        xa=Decimal("0.30"),
        xg_conceded=Decimal("1.10"),
        saves=2,
    )
