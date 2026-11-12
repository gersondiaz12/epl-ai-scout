"""Per-90 rates and percentiles, computed from stored totals. Deterministic: no
model or LLM is involved, and the same totals always give the same output.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal

from app.models import Position

# Below this many minutes a rate is too noisy to compare or rank.
PER90_MIN_MINUTES = 270


@dataclass(frozen=True)
class Totals:
    appearances: int = 0
    minutes: int = 0
    goals: int = 0
    assists: int = 0
    xg: Decimal = Decimal(0)
    xa: Decimal = Decimal(0)
    xg_conceded: Decimal = Decimal(0)
    saves: int = 0

    def __add__(self, other: "Totals") -> "Totals":
        return Totals(
            appearances=self.appearances + other.appearances,
            minutes=self.minutes + other.minutes,
            goals=self.goals + other.goals,
            assists=self.assists + other.assists,
            xg=self.xg + other.xg,
            xa=self.xa + other.xa,
            xg_conceded=self.xg_conceded + other.xg_conceded,
            saves=self.saves + other.saves,
        )


def sum_totals(items: Iterable[Totals]) -> Totals:
    total = Totals()
    for item in items:
        total = total + item
    return total


def per90(total: float | Decimal | int, minutes: int) -> float | None:
    """total / minutes * 90, or None when the player hasn't played enough."""
    if minutes < PER90_MIN_MINUTES:
        return None
    return float(total) / minutes * 90


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    total: Callable[[Totals], float | Decimal | int]
    higher_is_better: bool = True


METRICS: dict[str, Metric] = {
    m.key: m
    for m in [
        Metric("goals", "Goals", lambda t: t.goals),
        Metric("assists", "Assists", lambda t: t.assists),
        Metric("ga", "Goals + assists", lambda t: t.goals + t.assists),
        Metric("xg", "Expected goals (xG)", lambda t: t.xg),
        Metric("xa", "Expected assists (xA)", lambda t: t.xa),
        Metric("saves", "Saves", lambda t: t.saves),
        Metric("xg_conceded", "xG conceded", lambda t: t.xg_conceded, higher_is_better=False),
    ]
}

# Percentile panel metrics per position, most relevant first.
METRICS_BY_POSITION: dict[Position, list[str]] = {
    Position.GK: ["saves", "xg_conceded"],
    Position.DEF: ["xa", "assists", "xg", "goals"],
    Position.MID: ["ga", "xa", "assists", "xg", "goals"],
    Position.FWD: ["goals", "xg", "ga", "xa", "assists"],
}

# Per-90 values returned for every squad row.
SQUAD_PER90 = ["ga", "xg", "xa", "saves", "xg_conceded"]


def per90_values(totals: Totals, keys: Iterable[str] = SQUAD_PER90) -> dict[str, float | None]:
    return {key: per90(METRICS[key].total(totals), totals.minutes) for key in keys}


def percentile(value: float, pool: list[float], higher_is_better: bool = True) -> float:
    """Share of the pool this value beats, 0–100. Ties share the mid-rank, so a
    value equal to the whole pool scores 50. When lower is better (xG
    conceded), beating means having a lower value.
    """
    if not pool:
        raise ValueError("empty pool")
    if higher_is_better:
        beaten = sum(1 for v in pool if v < value)
    else:
        beaten = sum(1 for v in pool if v > value)
    ties = sum(1 for v in pool if v == value)
    return (beaten + ties / 2) / len(pool) * 100
