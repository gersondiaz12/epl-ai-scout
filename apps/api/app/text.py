"""Text normalisation for name search."""

import re
import unicodedata

# Letters with no Unicode decomposition, so stripping combining marks leaves
# them untouched (e.g. "Ødegaard" must match "Odegaard").
_TRANSLITERATE = str.maketrans(
    {
        "Ø": "O", "ø": "o",
        "Đ": "D", "đ": "d",
        "Ð": "D", "ð": "d",
        "Ł": "L", "ł": "l",
        "ı": "i",
        "ß": "ss",
        "Æ": "AE", "æ": "ae",
        "Œ": "OE", "œ": "oe",
        "Þ": "Th", "þ": "th",
    }
)  # fmt: skip
# Apostrophes and dots join ("O'Brien" -> "obrien", "J." -> "j"); anything else
# that isn't a letter or digit (hyphens, spaces) separates words.
_JOINERS = re.compile(r"['’‘`.]")
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase ASCII words separated by single spaces: "Martin Ødegaard" -> "martin odegaard"."""
    text = unicodedata.normalize("NFKD", text.translate(_TRANSLITERATE))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    text = _JOINERS.sub("", text)
    return _SEPARATORS.sub(" ", text).strip()
