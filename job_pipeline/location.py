"""Location signal parsing (pure, dependency-free).

Moved verbatim from shortlist.py during the scaffold phase — logic unchanged.

Conservative geo classifier for "can Henri (Estonia-based) actually take this
role". Geo tokens (cities/countries) are read from the LOCATION STRING only;
the description is consulted only for specific, low-false-positive phrases
(explicit US work-authorization, relocation, and remote-Europe wording), so an
"office in SF" mention in a JD body does not misclassify a role. Jobs are never
deleted on location — they are signalled and downranked.
"""

from __future__ import annotations

import html
import re
from typing import Any

# Signal values
SIG_ESTONIA_REMOTE_EU = "ESTONIA_OR_REMOTE_EU"
SIG_EU_ACTIONABLE = "EU_ACTIONABLE"
SIG_REMOTE_GLOBAL = "REMOTE_GLOBAL_OR_UNCLEAR"
SIG_HYBRID_EU = "HYBRID_EU"
SIG_NON_EU = "NON_EU_OR_US_ONSITE"
SIG_UNCLEAR = "LOCATION_UNCLEAR"

# Conservative score adjustment applied before track assignment.
LOCATION_ADJUSTMENT = {
    SIG_ESTONIA_REMOTE_EU: 12,
    SIG_EU_ACTIONABLE: 6,
    SIG_HYBRID_EU: -6,
    SIG_REMOTE_GLOBAL: 0,
    SIG_UNCLEAR: -4,
    SIG_NON_EU: -25,
}

_REMOTE_EU_PHRASES = [
    "remote europe", "europe remote", "remote eu", "eu remote",
    "emea remote", "remote emea", "remote from europe", "based in europe",
    "work from anywhere in europe", "anywhere in europe",
    "open to candidates in europe", "remote - europe", "remote, europe",
    "remote (europe)", "european union",
]
_ESTONIA = ["estonia", "tallinn"]
_EU_CITIES = [
    "berlin", "amsterdam", "paris", "dublin", "munich", "lisbon", "madrid",
    "barcelona", "warsaw", "prague", "vilnius", "riga", "helsinki",
    "stockholm", "copenhagen", "vienna",
]
_EU_COUNTRIES = [
    "germany", "netherlands", "france", "ireland", "portugal", "spain",
    "poland", "czech republic", "czechia", "lithuania", "latvia", "finland",
    "sweden", "denmark", "austria", "belgium", "italy", "luxembourg",
]
_UK = ["london", "united kingdom", "uk"]
_NON_EU_GEO = [
    "san francisco", "new york", "nyc", "boston", "seattle", "austin",
    "portland", "vancouver", "toronto", "singapore", "sydney", "melbourne",
    "são paulo", "sao paulo", "tel aviv", "palo alto", "mountain view",
    "denver", "atlanta", "miami", "chicago", "washington", "los angeles",
    "tokyo", "bangalore", "mumbai", "dubai", "abu dhabi",
    "united states", "usa", "canada", "australia", "brazil", "israel",
    "japan", "india", "united arab emirates", "morocco",
]
_US_ONLY_BLOCKERS = [
    "us only", "u.s. only", "us-only", "united states only",
    "must be based in the united states", "must be based in the us",
    "must reside in the united states", "must be located in the us",
    "authorized to work in the united states", "authorized to work in the us",
    "legally authorized to work in the united states",
    "based in the united states", "located in the united states",
    "u.s.-based", "us based", "us-based",
    "remote us", "us remote", "remote (us)", "remote - us", "remote, us",
]
_REMOTE_TOKENS = [
    "remote", "remote-friendly", "remote friendly", "worldwide",
    "distributed", "location flexible", "anywhere",
]
_REMOTE_DESC_PHRASES = [
    "fully remote", "remote-first", "remote first",
    "work from anywhere", "globally remote",
]
_OFFICE_DAYS = [
    "3 days in office", "3 days in the office", "three days in office",
    "2 days in office", "days in the office", "in-office", "in office",
]


def _clean(text: str) -> str:
    """Unescape HTML entities and strip tags to plain lowercase text."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", html.unescape(text)).lower()


def _loc_match(text: str, phrase: str) -> bool:
    """Word/phrase boundary match (case-insensitive), flexible whitespace."""
    pattern = r"\s+".join(re.escape(part) for part in phrase.lower().split())
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text) is not None


def _any(text: str, phrases: list[str]) -> bool:
    return any(_loc_match(text, p) for p in phrases)


def derive_location_signal(location: str, description: str) -> dict[str, Any]:
    """Classify a job's location actionability for an Estonia-based candidate.

    Returns {location_signal, location_blockers, location_notes}. Blockers win
    over positive signals (an explicit US-only requirement overrides "Remote").
    """
    loc = (location or "")
    L = loc.lower()
    D = _clean(description or "")
    both = L + " \n " + D

    blockers: list[str] = []
    notes: list[str] = []

    us_only = _any(both, _US_ONLY_BLOCKERS)
    reloc = _loc_match(both, "relocation required")
    onsite = _any(both, ["onsite only", "on-site only"])
    hybrid = _loc_match(L, "hybrid") or _any(both, _OFFICE_DAYS)

    estonia = _any(L, _ESTONIA)
    remote = _any(L, _REMOTE_TOKENS) or _any(D, _REMOTE_DESC_PHRASES)
    # A region word in the LOCATION string (not the JD body) + remote is a safe
    # "Remote - EMEA" / "Remote, Europe" signal even with punctuation between.
    eu_region_in_loc = _any(L, ["emea", "europe", "european"])
    remote_eu = _any(both, _REMOTE_EU_PHRASES) or (remote and eu_region_in_loc)
    eu_city = _any(L, _EU_CITIES)
    eu_country = _any(L, _EU_COUNTRIES)
    uk = _any(L, _UK)
    non_eu = _any(L, _NON_EU_GEO)
    eu_geo = eu_city or eu_country or uk  # an EU/UK office option is listed

    if us_only:
        blockers.append("US-only / US work authorization required")
        signal = SIG_NON_EU
    elif reloc:
        blockers.append("relocation required")
        signal = SIG_NON_EU
    elif onsite and not estonia:
        blockers.append(f"onsite only (non-Estonia): {loc.strip()}")
        signal = SIG_NON_EU
    elif estonia or remote_eu:
        # Explicit Estonia / Remote-Europe wins, even over hybrid wording.
        signal = SIG_ESTONIA_REMOTE_EU
    elif hybrid and eu_geo:
        notes.append("hybrid in EU city — confirm in-office days")
        if uk and not (eu_city or eu_country):
            notes.append("UK — visa/remote policy needs confirmation")
        if non_eu:
            notes.append("multi-region location; confirm Estonia/EU eligibility")
        signal = SIG_HYBRID_EU
    elif hybrid and non_eu:
        # Hybrid in US/non-EU city, no EU option and no explicit Remote-EU.
        blockers.append(f"hybrid in non-EU location: {loc.strip()}")
        signal = SIG_NON_EU
    elif eu_city or eu_country:
        if non_eu:
            notes.append("multi-region location; confirm Estonia/EU eligibility")
        signal = SIG_EU_ACTIONABLE
    elif uk:
        notes.append("UK — visa/remote policy needs confirmation")
        if non_eu:
            notes.append("multi-region location; confirm Estonia/EU eligibility")
        signal = SIG_EU_ACTIONABLE
    elif remote:
        if non_eu:
            notes.append("US/non-EU location present; confirm region eligibility")
        else:
            notes.append("remote/unclear — confirm region eligibility")
        signal = SIG_REMOTE_GLOBAL
    elif non_eu:
        blockers.append(f"non-EU / onsite location: {loc.strip()}")
        signal = SIG_NON_EU
    else:
        signal = SIG_UNCLEAR

    return {
        "location_signal": signal,
        "location_blockers": blockers,
        "location_notes": notes,
    }


def location_adjustment(signal: str) -> int:
    return LOCATION_ADJUSTMENT.get(signal, 0)


# Lower = more actionable for an Estonia-based candidate.
ACTIONABILITY_RANK = {
    SIG_ESTONIA_REMOTE_EU: 1,
    SIG_EU_ACTIONABLE: 2,
    SIG_HYBRID_EU: 3,
    SIG_REMOTE_GLOBAL: 4,
    SIG_UNCLEAR: 5,
    SIG_NON_EU: 6,
}


def actionability_rank(signal: str) -> int:
    return ACTIONABILITY_RANK.get(signal, 5)
