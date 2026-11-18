"""A tiny synthetic FPL payload, shaped like the real API (only the fields the
ingest reads). Two clubs, four players:

- Striker (ARS): 3 full matches, 1 goal each.
- Mover (MID): one match for COV, then one for ARS, where FPL lists them now.
- Keeper (COV): no minutes, so no match history.
- Forward (COV): 4 full matches, no goals.

FPL form: Striker 6.5, Mover 3.0, Keeper 0.0, Forward -0.8 (form can be negative).
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
        "starts": 1 if minutes >= 60 else 0,
        "tackles": 1,
        "clearances_blocks_interceptions": 2,
        "recoveries": 3,
        "goals_conceded": 1,
        "clean_sheets": 0,
        "penalties_saved": 0,
    }


# Season totals FPL reports per element, summed from the match history.
SUMMED = {
    key: key
    for key in (
        "starts",
        "tackles",
        "clearances_blocks_interceptions",
        "recoveries",
        "goals_conceded",
        "clean_sheets",
        "penalties_saved",
    )
}


HISTORIES: dict[int, list[dict[str, Any]]] = {
    101: [match(1, True, goals=1), match(2, False, goals=1), match(3, True, goals=1)],
    102: [match(1, False), match(2, False)],  # COV away at ARS, then ARS away at COV
    104: [match(1, False), match(2, True), match(3, False), match(4, True)],
}


def element(
    id_: int,
    code: int,
    name: str,
    team: int,
    element_type: int,
    birth: str | None,
    form: str = "0.0",
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
        **{key: sum(m[key] for m in history) for key in SUMMED},
        "form": form,
    }


def bootstrap() -> dict[str, Any]:
    return {
        "events": EVENTS,
        "teams": TEAMS,
        "elements": [
            element(101, 9001, "Striker", ARS, 4, "2000-01-15", form="6.5"),
            element(102, 9002, "Mover", ARS, 3, "1998-06-01", form="3.0"),
            element(103, 9003, "Keeper", COV, 1, None),
            element(104, 9004, "Forward", COV, 4, "1995-03-03", form="-0.8"),
        ],
    }


# ---------- Past seasons (element-summary history_past) ----------
# The current season is 2026-27, so the three seasons loaded are 2023-24 to 2025-26.


def past(code: int, season: str, minutes: int = 900, **overrides: Any) -> dict[str, Any]:
    row = {
        "season_name": season,
        "element_code": code,
        "minutes": minutes,
        "starts": 10 if minutes else 0,
        "goals_scored": 2,
        "assists": 1,
        "expected_goals": "1.50",
        "expected_assists": "0.80",
        "expected_goals_conceded": "12.30",
        "saves": 0,
        "tackles": 15,
        "clearances_blocks_interceptions": 30,
        "recoveries": 40,
        "goals_conceded": 11,
        "clean_sheets": 3,
        "penalties_saved": 0,
    }
    if minutes == 0:  # no minutes: every count is 0
        row = {
            k: ("0.00" if isinstance(v, str) and "." in v else 0)
            if k not in ("season_name", "element_code")
            else v
            for k, v in row.items()
        }
    return row | overrides


def summaries() -> list[dict[str, Any]]:
    """One element-summary per player, history only.

    - Striker (9001): 2025/26 complete; 2024/25 before FPL tracked tackles, CBI and
      recoveries (all players 0 that season); 2019/20 outside the range.
    - Mover (9002): on FPL's books in 2023/24 but no minutes.
    - Forward (9004): a 2024/25 row with an unreadable xG value.
    - An element code we don't know (7777): can't be linked.
    """
    return [
        {
            "history_past": [
                past(9001, "2019/20"),
                past(9001, "2024/25", tackles=0, clearances_blocks_interceptions=0, recoveries=0),
                past(9001, "2025/26"),
            ]
        },
        {"history_past": [past(9002, "2023/24", minutes=0)]},
        {"history_past": []},
        {"history_past": [past(9004, "2024/25", expected_goals="abc")]},
        {"history_past": [past(7777, "2025/26")]},
    ]
