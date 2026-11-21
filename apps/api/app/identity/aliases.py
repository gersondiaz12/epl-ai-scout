"""Reviewed alias tables for player matching (rule R3).

Every entry comes from a real pair in our data, checked by hand: both sides
share a birth date and are the same person. Add entries only after checking a
real case; the table's hash is recorded with every match run.
"""

import hashlib

# Given names that are the same name (diminutives, local forms), normalised.
GIVEN_NAME_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"ben", "benjamin"}),  # Benjamin White / Ben White
    frozenset({"dan", "daniel"}),  # Dan Bentley / Daniel Bentley, Daniel Ballard / Dan Ballard
    frozenset({"kostas", "konstantinos"}),  # Kostas Tsimikas / Konstantinos Tsimikas
    frozenset({"sam", "sammie"}),  # Sam Szmodics / Sammie Szmodics
)

# Whole names that are the same person, normalised, for one-word names that no
# other rule can link safely.
FULL_NAME_PAIRS: tuple[frozenset[str], ...] = (
    frozenset({"savio", "savinho"}),  # Sávio (FPL) / Savinho (Transfermarkt)
    frozenset({"alisson becker", "alisson"}),  # Alisson Becker / Alisson
    frozenset({"gabriel magalhaes", "gabriel"}),  # Gabriel Magalhães / Gabriel, 1997-12-19
)


def given_alias(a: str, b: str) -> bool:
    return any(a in group and b in group for group in GIVEN_NAME_GROUPS)


def full_alias(a: str, b: str) -> bool:
    return a != b and frozenset({a, b}) in FULL_NAME_PAIRS


def table_hash() -> str:
    text = repr(
        (
            sorted(sorted(g) for g in GIVEN_NAME_GROUPS),
            sorted(sorted(p) for p in FULL_NAME_PAIRS),
        )
    )
    return hashlib.sha256(text.encode()).hexdigest()[:16]
