"""Name normalisation for matching.

Builds on app.text.normalize (accents, letters with no decomposition) and adds:
- dots separate words, so FPL display names like "J.Timber" give "j timber";
- the "jr" suffix is dropped;
- "dj" folds to "d" on both sides, so Serbian/Croatian Đ ("Đorđe", which
  normalises to "dorde") equals its "Dj" spelling ("Djordje");
- a hyphenated name also counts with its parts joined ("Ji-soo" = "Jisoo").
"""

import re
from difflib import SequenceMatcher

from app.text import normalize

PARTICLES = frozenset(
    {"de", "da", "do", "dos", "das", "di", "del", "della", "van", "von", "der", "den", "ter"}
    | {"le", "la", "du", "el", "al"}
)
SUFFIXES = frozenset({"jr"})


def words(name: str) -> tuple[str, ...]:
    """Normalised words in written order: "Đorđe Petrović" -> ("dorde", "petrovic")."""
    text = normalize(name.replace(".", " "))
    return tuple(w.replace("dj", "d") for w in text.split() if w not in SUFFIXES)


def word_sets(name: str) -> set[frozenset[str]]:
    """The name's word set, plus the one with hyphenated parts joined."""
    joined = re.sub(r"(?<=\w)-(?=\w)", "", name)
    return {frozenset(words(name)), frozenset(words(joined))}


def core(ws) -> set[str]:
    """Words that can identify someone: no particles, no initials."""
    return {w for w in ws if w not in PARTICLES and len(w) > 1}


def given_names_agree(a: str, b: str, *, aliases: bool) -> bool:
    """Equal, an initial of the other ("j" / "jurrien"), or (with aliases) a nickname pair."""
    if a == b:
        return True
    if len(a) == 1 or len(b) == 1:
        return a[0] == b[0]
    if aliases:
        from app.identity.aliases import given_alias

        return given_alias(a, b)
    return False


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def aligned_score(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Each word of the shorter name against its best match in the longer one;
    the weakest of those is the score. 1.0 when every word has an exact match."""
    if not a or not b:
        return 0.0
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return min(max(ratio(s, w) for w in long_) for s in short)
