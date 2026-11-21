"""Matching stages, as pure functions, on real awkward names from our data.

Each pair is (FPL name, Transfermarkt name) as the two sources spell them.
Birth dates are real where the case depends on one; otherwise any shared date.
"""

from datetime import date

import pytest

from app.identity.aliases import table_hash
from app.identity.names import aligned_score, words
from app.identity.stages import MARGIN, THRESHOLD, Person, assign, evaluate, settings

D = date(2000, 1, 1)


def ours(name, dob=D, clubs=(), key="1"):
    return Person(key, (name,), dob, frozenset(clubs))


def tm(name, dob=D, clubs=(), key="a", *more):
    return Person(key, (name, *more), dob, frozenset(clubs), "Club")


def method(a, b, dob=D):
    return evaluate(ours(a, dob), tm(b, dob)).method


# ---------- Normalisation ----------


def test_words():
    assert words("Martin Ødegaard") == ("martin", "odegaard")
    assert words("Đorđe Petrović") == words("Djordje Petrovic")  # Đ = Dj
    assert words("J.Timber") == ("j", "timber")  # dots separate in display names
    assert words("Kroupi.Jr") == ("kroupi",)
    assert words("Jake O'Brien") == ("jake", "obrien")


# ---------- Rules ----------


@pytest.mark.parametrize(
    "fpl, transfermarkt",
    [
        ("Martin Ødegaard", "Martin Odegaard"),
        ("Ferdi Kadıoğlu", "Ferdi Kadioglu"),
        ("Abdülkadir Ömür", "Abdulkadir Omur"),
        ("Đorđe Petrović", "Djordje Petrovic"),
        ("Mitoma Kaoru", "Kaoru Mitoma"),
        ("Tanaka Ao", "Ao Tanaka"),
        ("Endo Wataru", "Wataru Endo"),
        ("Kim Ji-Soo", "Ji-soo Kim"),
        ("Son Heung-min", "Heung-Min Son"),  # synthetic: not in our data
        ("Kim Ji-Soo", "Kim Jisoo"),  # hyphen joined
        ("Aaron Wan-Bissaka", "Aaron Wan-Bissaka"),
    ],
)
def test_r1_same_words_in_any_order(fpl, transfermarkt):
    assert method(fpl, transfermarkt) == "r1_same_words"


@pytest.mark.parametrize(
    "fpl, transfermarkt",
    [
        ("David Raya Martín", "David Raya"),
        ("Dominic Solanke-Mitchell", "Dominic Solanke"),
        ("Levi Samuels Colwill", "Levi Colwill"),
        ("Gabriel dos Santos Magalhães", "Gabriel Magalhães"),
    ],
)
def test_r2_extra_surnames(fpl, transfermarkt):
    assert method(fpl, transfermarkt) == "r2_subset"


@pytest.mark.parametrize(
    "fpl, transfermarkt",
    [
        ("Benjamin White", "Ben White"),
        ("Dan Bentley", "Daniel Bentley"),
        ("Daniel Ballard", "Dan Ballard"),
        ("Kostas Tsimikas", "Konstantinos Tsimikas"),
        ("Sam Szmodics", "Sammie Szmodics"),
        ("Sávio", "Savinho"),
        ("Alisson Becker", "Alisson"),
        ("Gabriel Magalhães", "Gabriel"),
    ],
)
def test_r3_reviewed_aliases(fpl, transfermarkt):
    assert method(fpl, transfermarkt) == "r3_alias"


@pytest.mark.parametrize(
    "fpl, transfermarkt, score",
    [
        ("Yehor Yarmoliuk", "Yegor Yarmolyuk", 0.8),
        ("Tymur Tutierov", "Timur Tuterov", 0.8),
        ("Vitalii Mykolenko", "Vitaliy Mykolenko", 0.857),
    ],
)
def test_fuzzy_transliterations(fpl, transfermarkt, score):
    ev = evaluate(ours(fpl), tm(transfermarkt))
    assert ev.method == "fuzzy" and ev.score == pytest.approx(score, abs=0.001)


# ---------- Must not link ----------


@pytest.mark.parametrize(
    "fpl, transfermarkt",
    [
        ("Jurriën Timber", "Quinten Timber"),  # twins, same birth date
        ("Tyler Fletcher", "Jack Fletcher"),
        ("Ryan Sessegnon", "Steven Sessegnon"),
        ("Jacob Murphy", "Josh Murphy"),
        ("Michael Keane", "Will Keane"),
    ],
)
def test_twins_and_brothers_born_the_same_day_never_link(fpl, transfermarkt):
    ev = evaluate(ours(fpl), tm(transfermarkt))
    assert ev.method is None and ev.score < THRESHOLD
    assert ev.failed_on in {"no_name_match", "below_threshold"}  # Timber twins score 0.57


def test_one_word_names_never_go_fuzzy():
    # 0.80 would pass the threshold: one-word names are excluded instead.
    assert aligned_score(words("Remi Matthews"), words("Matheus")) == pytest.approx(0.8)
    ev = evaluate(ours("Remi Matthews"), tm("Matheus"))
    assert ev.method is None and ev.failed_on == "one_word_name"
    assert evaluate(ours("Florentino"), tm("Laorent Shabani")).method is None
    # A weak one-word candidate is just no match (Harvey Cartwright / "Daniel Jr").
    ev = evaluate(ours("Harvey Cartwright"), tm("Daniel Jr"))
    assert ev.failed_on == "no_name_match"


def test_threshold_separates_the_real_near_misses():
    """Regression: the closest true pairs score 0.80, the closest wrong pairs
    are one-word names or twins. Changing THRESHOLD must keep this split."""
    true_lowest = min(
        aligned_score(words(a), words(b))
        for a, b in [("Yehor Yarmoliuk", "Yegor Yarmolyuk"), ("Tymur Tutierov", "Timur Tuterov")]
    )
    twins_highest = max(
        aligned_score(words(a), words(b))
        for a, b in [("Jurriën Timber", "Quinten Timber"), ("Jacob Murphy", "Josh Murphy")]
    )
    assert twins_highest < THRESHOLD <= true_lowest
    assert settings() == {
        "matcher_version": "1",
        "threshold": THRESHOLD,
        "margin": MARGIN,
        "alias_table": table_hash(),
    }


def test_different_birth_dates_never_link():
    ev = evaluate(ours("Martin Ødegaard", D), tm("Martin Odegaard", date(1998, 12, 17)))
    assert ev.method is None and ev.failed_on == "different_birth_date"


def test_dotted_display_names_never_decide():
    # Only full names are matched; an initial plus a shared surname isn't a full name.
    assert method("J Timber", "Quinten Timber") is None


# ---------- No birth date: club evidence ----------


def test_no_birth_date_needs_the_same_club():
    shepherd = ours("George Shepherd", None, clubs={7})
    assert evaluate(shepherd, tm("George Shepherd", None, clubs={7})).method == "r4_club"
    ev = evaluate(shepherd, tm("George Shepherd", None, clubs={11}))
    assert ev.method is None and ev.failed_on == "no_birth_date"


def test_a_transferred_player_matches_either_club():
    # Iliman Ndiaye: Everton (9) then Manchester City (15) this season.
    ndiaye = ours("Iliman Ndiaye", None, clubs={9, 15})
    assert evaluate(ndiaye, tm("Iliman Ndiaye", None, clubs={15})).method == "r4_club"
    assert evaluate(ndiaye, tm("Iliman Ndiaye", None, clubs={9})).method == "r4_club"


# ---------- Assignment ----------


def test_liam_kitching_is_unmatched_with_his_three_candidates():
    dob = date(1999, 9, 25)
    result = assign(
        [ours("Liam Kitching", dob)],
        [
            tm("Vladislav Kreida", dob, key="356892"),
            tm("Uran Bislimi", dob, key="461461"),
            tm("Edwin Rodríguez", dob, key="627408"),
        ],
    )
    reason, cands = result.unmatched["1"]
    assert reason == "no_name_match"
    assert {c["key"] for c in cands} == {"356892", "461461", "627408"}
    assert all(c["failed_on"] == "no_name_match" for c in cands)


def test_same_surname_in_our_own_data_links_each_to_their_own():
    a, b = date(2005, 1, 1), date(2002, 2, 2)
    result = assign(
        [ours("Mamadou Sarr", a, key="1"), ours("Pape Matar Sarr", b, key="2")],
        [tm("Mamadou Sarr", a, key="x"), tm("Pape Matar Sarr", b, key="y")],
    )
    assert {k: v[0] for k, v in result.links.items()} == {"1": "x", "2": "y"}


def test_reasons():
    result = assign(
        [
            ours("Nobody Here", date(1990, 1, 1), key="1"),
            ours("Keeper Name", None, key="2"),
            ours("Alex Smith", D, key="3"),
        ],
        [tm("Alex Brown", D, key="a"), tm("Alex Green", D, key="b")],
    )
    assert {k: v[0] for k, v in result.unmatched.items()} == {
        "1": "not_in_source",
        "2": "no_birth_date",
        "3": "no_name_match",
    }


def test_two_equal_candidates_are_ambiguous_unless_the_club_decides():
    o = ours("Chris Wood", D, clubs={18})
    a, b = tm("Chris Wood", D, key="a", clubs={18}), tm("Chris Wood", D, key="b")
    assert assign([o], [a, b]).links["1"][0] == "a"
    assert assign([ours("Chris Wood")], [a, b]).unmatched["1"][0] == "ambiguous"


def test_fuzzy_needs_a_margin():
    o = ours("Yehor Yarmoliuk")
    close = [tm("Yegor Yarmolyuk", key="a"), tm("Yegor Yarmoluk", key="b")]
    assert assign([o], close).unmatched["1"][0] == "ambiguous"
    assert assign([o], close[:1]).links["1"][0] == "a"


def test_one_record_claimed_by_two_of_ours_links_neither():
    twins = [ours("Chris Wood", key="1"), ours("Chris Wood", key="2")]
    result = assign(twins, [tm("Chris Wood")])
    assert result.links == {} and {v[0] for v in result.unmatched.values()} == {"ambiguous"}


def test_rejected_and_taken():
    o, a = ours("Martin Ødegaard"), tm("Martin Odegaard")
    assert assign([o], [a], rejected={("1", "a")}).unmatched["1"][0] == "rejected_by_operator"
    assert assign([o], [a], taken={"a"}).unmatched["1"][0] == "target_already_linked"


def test_assignment_is_deterministic():
    people = [ours(f"Player {i}", key=str(i)) for i in range(5)]
    recs = [tm(f"Player {i}", key=f"r{i}") for i in reversed(range(5))]
    assert assign(people, recs).links == assign(list(reversed(people)), recs).links
