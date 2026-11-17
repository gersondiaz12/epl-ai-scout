import pytest

from app.routers.search import match_rank
from app.text import normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Martin Ødegaard", "martin odegaard"),  # Ø has no Unicode decomposition
        ("Đorđe Petrović", "dorde petrovic"),
        ("Kadıoğlu", "kadioglu"),  # dotless i
        ("Weißmann", "weissmann"),
        ("Benoît Badiashile", "benoit badiashile"),
        ("Dominic Solanke-Mitchell", "dominic solanke mitchell"),
        ("Dara O'Shea", "dara oshea"),
        ("J. Timber", "j timber"),
        ("  ODEGAARD  ", "odegaard"),
        ("", ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_match_rank_orders_exact_then_word_start_then_substring():
    names = ["martin odegaard", "odegaard"]
    assert match_rank("odegaard", names) == 0  # exact display name
    assert match_rank("mart ode", names) == 1  # each word starts a name word
    assert match_rank("egaard", names) == 2  # inside a word
    assert match_rank("saka", names) is None
    assert match_rank("", names) == 0
