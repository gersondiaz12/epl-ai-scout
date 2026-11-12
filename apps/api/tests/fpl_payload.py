"""A tiny synthetic FPL payload, shaped like the real API (only the fields the
ingest reads). Two clubs, four players:

- Striker (ARS): 3 full matches, 1 goal each.
- Mover (MID): one match for COV, then one for ARS, where FPL lists them now.
- Keeper (COV): no minutes, so no match history.
- Forward (COV): 4 full matches, no goals.
"""

from typing import Any

ARS, COV = 1, 2  # per-season FPL team ids
TEAMS = [
    {"id": ARS, "code": 3, "name": "Arsenal", "short_name": "ARS"},
    {"id": COV, "code": 9, "name": "Coventry", "short_name": "COV"},
]
EVENTS = [
    {"id": 1, "deadline_time": "2026-08-21T17:30:00Z"},
    {"id": 38, "deadline_time": "2027-05-30T13:30:00Z"},
]
# Fixture 1: ARS (home) v COV. Fixture 2: COV (home) v ARS. Fixtures 3-4: ARS v COV again.
FIXTURES = [
    {"id": 1, "team_h": ARS, "team_a": COV},
    {"id": 2, "team_h": COV, "team_a": ARS},
    {"id": 3, "team_h": ARS, "team_a": COV},
    {"id": 4, "team_h": COV, "team_a": ARS},
]


def match(
    fixture: int, was_home: bool, minutes: int = 90, goals: int = 0, saves: int = 0
) -> dict[str, Any]:
    return {
        "fixture": fixture,
        "was_home": was_home,
        "minutes": minutes,
        "goals_scored": goals,
        "assists": 0,
        "expected_goals": "0.50" if goals else "0.10",
        "expected_assists": "0.00",
        "expected_goals_conceded": "1.00",
        "saves": saves,
    }


HISTORIES: dict[int, list[dict[str, Any]]] = {
    101: [match(1, True, goals=1), match(2, False, goals=1), match(3, True, goals=1)],
    102: [match(1, False), match(2, False)],  # COV away at ARS, then ARS away at COV
    104: [match(1, False), match(2, True), match(3, False), match(4, True)],
}


def element(
    id_: int, code: int, name: str, team: int, element_type: int, birth: str | None
) -> dict[str, Any]:
    history = HISTORIES.get(id_, [])
    return {
        "id": id_,
        "code": code,
        "first_name": name,
        "second_name": "Test",
        "web_name": name,
        "team": team,
        "element_type": element_type,
        "birth_date": birth,
        "minutes": sum(m["minutes"] for m in history),
        "goals_scored": sum(m["goals_scored"] for m in history),
        "assists": 0,
        "expected_goals": f"{sum(float(m['expected_goals']) for m in history):.2f}",
        "expected_assists": "0.00",
        "saves": sum(m["saves"] for m in history),
    }


def bootstrap() -> dict[str, Any]:
    return {
        "events": EVENTS,
        "teams": TEAMS,
        "elements": [
            element(101, 9001, "Striker", ARS, 4, "2000-01-15"),
            element(102, 9002, "Mover", ARS, 3, "1998-06-01"),
            element(103, 9003, "Keeper", COV, 1, None),
            element(104, 9004, "Forward", COV, 4, "1995-03-03"),
        ],
    }
