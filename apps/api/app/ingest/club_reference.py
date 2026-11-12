"""Club facts FPL doesn't provide (full name, ground, city), keyed by FPL's team code.

Update this when clubs are promoted. A club missing from this table is still
ingested; it gets a slug from its name and no ground or city.
"""

from typing import NamedTuple


class ClubReference(NamedTuple):
    slug: str
    name: str  # full name; FPL uses informal ones such as 'Man Utd' and 'Spurs'
    ground: str
    city: str


CLUB_REFERENCE: dict[int, ClubReference] = {
    3: ClubReference("arsenal", "Arsenal", "Emirates Stadium", "London"),
    7: ClubReference("aston-villa", "Aston Villa", "Villa Park", "Birmingham"),
    91: ClubReference("bournemouth", "Bournemouth", "Vitality Stadium", "Bournemouth"),
    94: ClubReference("brentford", "Brentford", "Gtech Community Stadium", "London"),
    36: ClubReference("brighton", "Brighton & Hove Albion", "American Express Stadium", "Brighton"),
    8: ClubReference("chelsea", "Chelsea", "Stamford Bridge", "London"),
    9: ClubReference(
        "coventry-city", "Coventry City", "Coventry Building Society Arena", "Coventry"
    ),
    31: ClubReference("crystal-palace", "Crystal Palace", "Selhurst Park", "London"),
    11: ClubReference("everton", "Everton", "Hill Dickinson Stadium", "Liverpool"),
    54: ClubReference("fulham", "Fulham", "Craven Cottage", "London"),
    88: ClubReference("hull-city", "Hull City", "MKM Stadium", "Hull"),
    40: ClubReference("ipswich-town", "Ipswich Town", "Portman Road", "Ipswich"),
    2: ClubReference("leeds-united", "Leeds United", "Elland Road", "Leeds"),
    14: ClubReference("liverpool", "Liverpool", "Anfield", "Liverpool"),
    43: ClubReference("manchester-city", "Manchester City", "Etihad Stadium", "Manchester"),
    1: ClubReference("manchester-united", "Manchester United", "Old Trafford", "Manchester"),
    4: ClubReference("newcastle-united", "Newcastle United", "St James' Park", "Newcastle"),
    17: ClubReference("nottingham-forest", "Nottingham Forest", "City Ground", "Nottingham"),
    56: ClubReference("sunderland", "Sunderland", "Stadium of Light", "Sunderland"),
    6: ClubReference(
        "tottenham-hotspur", "Tottenham Hotspur", "Tottenham Hotspur Stadium", "London"
    ),
}

# Clubs promoted into each season, by FPL team code.
PROMOTED: dict[str, set[int]] = {
    "2026-27": {9, 40, 88},  # Coventry City, Ipswich Town, Hull City
}
