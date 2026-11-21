"""The matching stages as pure functions: no database, same input -> same output.

Order (the first decisive stage wins):
  0. manual decisions (applied by the caller: forced links, rejected pairs, no_match)
  1. exact key: links already stored are kept (the caller passes them in)
  2. rules, same birth date unless stated:
     R1 same name words in any order; R2 one name's words within the other's,
     given names agree; R3 equal after the reviewed alias table;
     R4 no birth date on one side: R1/R2/R3 plus the same club this season
  3. fuzzy: same birth date, both names 2+ words, word-aligned score >= THRESHOLD
     and at least MARGIN ahead of the next candidate
  4. everything else is unmatched, with a reason and its candidates
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.identity.aliases import full_alias, table_hash
from app.identity.names import aligned_score, core, given_names_agree, word_sets, words

MATCHER_VERSION = "1"
THRESHOLD = 0.75  # real data: 649/654 true pairs >= 0.75, 0/4,544 same-birth-date others
MARGIN = 0.10
MAX_CANDIDATES = 5

RANK = {"r1_same_words": 6, "r2_subset": 5, "r3_alias": 4, "fuzzy": 3, "r4_club": 2}


def settings() -> dict:
    return {
        "matcher_version": MATCHER_VERSION,
        "threshold": THRESHOLD,
        "margin": MARGIN,
        "alias_table": table_hash(),
    }


@dataclass(frozen=True)
class Person:
    """One side of a pair: one of our players (key = player id) or a source record
    (key = external id). `names` holds every full name the side is known by."""

    key: str
    names: tuple[str, ...]
    birth_date: date | None
    club_ids: frozenset[int] = frozenset()  # our club ids at the record's date / this season
    club_name: str | None = None

    @property
    def label(self) -> str:
        return self.names[0] if self.names else self.key


@dataclass(frozen=True)
class Evidence:
    method: str | None  # None: a candidate, but nothing decisive
    score: float  # word-aligned name score
    failed_on: str | None = None  # why a candidate didn't link

    @property
    def rank(self) -> int:
        return RANK.get(self.method or "", 0)


def _name_rule(a: str, b: str) -> str | None:
    """R1, R2 or R3 between two full names, ignoring dates and clubs."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return None
    if word_sets(a) & word_sets(b):
        return "r1_same_words"
    if full_alias(" ".join(wa), " ".join(wb)):
        return "r3_alias"
    short, long_ = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    if len(core(short)) >= 2 and set(short) <= set(long_):
        if given_names_agree(short[0], long_[0], aliases=False):
            return "r2_subset"
        if given_names_agree(short[0], long_[0], aliases=True):
            return "r3_alias"
    # A nickname given name with the same family words: "Ben White" / "Benjamin White".
    if (
        len(wa) >= 2
        and len(wb) >= 2
        and wa[1:] == wb[1:]
        and given_names_agree(wa[0], wb[0], aliases=True)
    ):
        return "r3_alias"
    return None


def evaluate(ours: Person, rec: Person) -> Evidence:
    """The strongest evidence that `ours` and `rec` are the same person."""
    pairs = [(a, b) for a in ours.names for b in rec.names]
    score = max((aligned_score(words(a), words(b)) for a, b in pairs), default=0.0)
    rules = [r for r in (_name_rule(a, b) for a, b in pairs) if r]
    rule = max(rules, key=RANK.__getitem__) if rules else None
    same_club = bool(ours.club_ids & rec.club_ids)

    if ours.birth_date and rec.birth_date:
        if ours.birth_date != rec.birth_date:
            return Evidence(None, score, "different_birth_date")
        if rule:
            return Evidence(rule, score)
        if score >= THRESHOLD:
            # A one-word name would pass on too little evidence ("Matheus" /
            # "Remi Matthews" scores 0.80): only the alias table can link it.
            if any(len(core(words(n))) < 2 for n in ours.names[:1] + rec.names[:1]):
                return Evidence(None, score, "one_word_name")
            return Evidence("fuzzy", score)
        return Evidence(None, score, "below_threshold" if score >= 0.5 else "no_name_match")

    # No birth date on at least one side: a name rule plus the same club.
    if rule and same_club:
        return Evidence("r4_club", score)
    return Evidence(None, score, "no_birth_date" if rule else "no_name_match")


@dataclass
class Assignment:
    links: dict[str, tuple[str, Evidence]] = field(default_factory=dict)  # ours -> (rec, ev)
    unmatched: dict[str, tuple[str, list[dict]]] = field(default_factory=dict)  # ours -> reason


def candidate_entry(p: Person, ev: Evidence) -> dict:
    return {
        "key": p.key,
        "name": p.label,
        "birth_date": p.birth_date.isoformat() if p.birth_date else None,
        "club": p.club_name,
        "stage": ev.method,
        "score": round(ev.score, 3),
        "failed_on": ev.failed_on,
    }


def block(records: list[Person]):
    """Index records by birth date and by identifying word, for candidate lookup."""
    by_dob: dict[date, list[Person]] = defaultdict(list)
    by_word: dict[str, list[Person]] = defaultdict(list)
    for r in records:
        if r.birth_date:
            by_dob[r.birth_date].append(r)
        for w in {w for n in r.names for w in core(words(n)) if len(w) >= 3}:
            by_word[w].append(r)
    return by_dob, by_word


def candidates_for(o: Person, by_dob, by_word) -> list[Person]:
    found: dict[str, Person] = {}
    if o.birth_date:
        for r in by_dob.get(o.birth_date, []):
            found[r.key] = r
    # Without a birth date on either side, only a shared name word makes a candidate.
    for w in {w for n in o.names for w in core(words(n)) if len(w) >= 3}:
        for r in by_word.get(w, []):
            if o.birth_date is None or r.birth_date is None:
                found[r.key] = r
    return [found[k] for k in sorted(found)]


def assign(
    ours: list[Person],
    records: list[Person],
    *,
    taken: set[str] = frozenset(),  # record keys already linked to someone else
    rejected: set[tuple[str, str]] = frozenset(),  # (our key, record key) never to link
) -> Assignment:
    """Propose one record for each of `ours`, deterministically. Pure."""
    by_dob, by_word = block(records)
    result = Assignment()
    for o in sorted(ours, key=lambda p: p.key):
        cands = candidates_for(o, by_dob, by_word)
        evs = [(r, evaluate(o, r)) for r in cands]
        listed = sorted(evs, key=lambda x: (-x[1].rank, -x[1].score, x[0].key))[:MAX_CANDIDATES]
        entries = [candidate_entry(r, ev) for r, ev in listed]
        live = [(r, ev) for r, ev in evs if (o.key, r.key) not in rejected]
        decisive = [(r, ev) for r, ev in live if ev.rank > 0]

        if not decisive:
            if any(ev.rank > 0 for r, ev in evs):
                reason = "rejected_by_operator"
            elif o.birth_date is None:
                reason = "no_birth_date"
            elif not any(r.birth_date == o.birth_date for r in cands):
                reason = "not_in_source"
            else:
                fails = {ev.failed_on for _, ev in live if ev.failed_on}
                reason = next(
                    (f for f in ("below_threshold", "one_word_name") if f in fails),
                    "no_name_match",
                )
            result.unmatched[o.key] = (reason, entries)
            continue

        best = max(ev.rank for _, ev in decisive)
        top = [(r, ev) for r, ev in decisive if ev.rank == best]
        if len(top) > 1:
            same_club = [(r, ev) for r, ev in top if o.club_ids & r.club_ids]
            top = same_club if len(same_club) == 1 else top
        if len(top) > 1:
            result.unmatched[o.key] = ("ambiguous", entries)
            continue
        rec, ev = top[0]
        if ev.method == "fuzzy":
            others = [
                e.score
                for r, e in live
                if r.key != rec.key and e.failed_on != "different_birth_date"
            ]
            if others and ev.score - max(others) < MARGIN:
                result.unmatched[o.key] = ("ambiguous", entries)
                continue
        if rec.key in taken:
            result.unmatched[o.key] = ("target_already_linked", entries)
            continue
        result.links[o.key] = (rec.key, ev)

    # A record proposed for two of ours links neither.
    claims: dict[str, list[str]] = defaultdict(list)
    for o_key, (r_key, _) in result.links.items():
        claims[r_key].append(o_key)
    for r_key, o_keys in claims.items():
        if len(o_keys) > 1:
            for o_key in o_keys:
                del result.links[o_key]
                result.unmatched[o_key] = ("ambiguous", [{"key": r_key, "claimed_by": o_keys}])
    return result
