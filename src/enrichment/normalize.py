"""Company-name normalization and blocking keys for entity resolution.

The goal is not a pretty name - it is a *stable, collision-tolerant key* that
lets us block 11k input names against a 3M-row reference file without doing
11k x 3M comparisons.
"""

from __future__ import annotations

import re
import unicodedata

# Legal forms, longest-first so "s.p.a" is stripped before "sa".
LEGAL_FORMS = [
    "aktiengesellschaft",
    "incorporated",
    "corporation",
    "limited liability company",
    "public limited company",
    "proprietary limited",
    "besloten vennootschap",
    "naamloze vennootschap",
    "sociedad anonima",
    "societe anonyme",
    "kabushiki kaisha",
    "aktiebolag",
    "aktieselskab",
    "s p a",
    "s r l",
    "s a s",
    "s a r l",
    "s a",
    "b v",
    "n v",
    "a s",
    "a p s",
    "gmbh co kg",
    "gmbh",
    "mbh",
    "ag",
    "kgaa",
    "kg",
    "ohg",
    "se",
    "plc",
    "ltd",
    "llc",
    "llp",
    "lp",
    "inc",
    "corp",
    "co",
    "pty",
    "pte",
    "pvt",
    "pjsc",
    "jsc",
    "ojsc",
    "oao",
    "ooo",
    "zao",
    "srl",
    "sarl",
    "sas",
    "spa",
    "sca",
    "sprl",
    "bvba",
    "cvba",
    "oy",
    "oyj",
    "ab",
    "asa",
    "aps",
    "kft",
    "zrt",
    "nyrt",
    "doo",
    "dd",
    "sp z o o",
    "sp zoo",
    "spolka akcyjna",
    "tov",
    "pat",
    # compact spellings that survive folding: "B.V."->"b v" but "BV"->"bv"
    "bv",
    "nv",
    "sa",
    "as",
    "aps",
    "sl",
    "sp",
    "kgaa",
    # --- regional forms found by auditing the parked tier of a real list ---
    "s de r l de c v",
    "sa de c v",
    "de r l de c v",
    "de c v",
    "de r l",
    "s de r l",
    "c v",
    "r l",
    "sapi",
    "scv",  # Mexico / LatAm
    "ltda",
    "limitada",
    "eireli",
    "s a",  # Brazil / Portugal
    "sdn bhd",
    "sdn",
    "bhd",
    "berhad",  # Malaysia / Brunei
    "pt",
    "tbk",
    "persero",  # Indonesia
    "k k",
    "y k",
    "godo kaisha",
    "gk",  # Japan
    "s r o",
    "sro",
    "a s",
    "k s",  # Czech / Slovak
    "s l",
    "s l u",
    "slu",
    "s c",
    "sc",
    "scl",
    "sll",  # Spain
    "spolka",
    "sp j",
    "s j",
    "sk a",  # Poland
    "co ltd",
    "company limited",
    "int",
    "intl",
    "d o o",
    "a d",
    "e o o d",
    "o o o",  # Balkans / CIS
    "ind",
    "com",
    "cia",
    "s a i c",
    "srl cv",
    "kk",
    "yk",
    "cv",
    "vof",
    "eurl",
    "snc",
    "scs",
    "sca",
    "limited",
    "holdings",
    "holding",
    "group",
    "groupe",
    "gruppe",
]
_FORM_RE = re.compile(r"\b(" + "|".join(re.escape(f) for f in LEGAL_FORMS) + r")\b")

# Site/role qualifiers that appear in facility lists but never in a registry.
_QUALIFIER_RE = re.compile(
    r"\b(hq|headquarters|head office|global|worldwide|division|div|plant|site|"
    r"facility|works|factory|branch|office|region|regional|emea|apac|latam|"
    r"north america|europe|asia pacific)\b"
)

# "Acme Foods (Malaysia)" -> qualifier is a place, not part of the legal name.
_PAREN_RE = re.compile(r"\s*\([^)]*\)")

# Leading articles carry no identity ("The Unilever Group" == "Unilever PLC").
_LEAD_ARTICLE_RE = re.compile(r"^(the|la|le|les|el|il|de|het|een)\s+")
# "&" folds to "and"; once "Co. KG" is stripped it dangles at the edges.
_DANGLING_RE = re.compile(r"^(and|of|for)\s+|\s+(and|of|for)$")


def _fold(s: str) -> str:
    """Unicode -> ASCII lowercase, punctuation to spaces, whitespace collapsed."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean(name: str) -> str:
    """Human-readable normalized name. Keeps word order, drops legal noise."""
    s = _PAREN_RE.sub(" ", name or "")
    s = _fold(s)
    s = _QUALIFIER_RE.sub(" ", s)
    s = _LEAD_ARTICLE_RE.sub("", s)
    prev = None
    while prev != s:  # strip forms repeatedly:
        prev = s  # "acme industries gmbh co kg" -> "acme industries"
        s = _FORM_RE.sub(" ", s)
        s = re.sub(r"\s+", " ", s).strip()
        s = _DANGLING_RE.sub("", s).strip()
    return s or _fold(_PAREN_RE.sub(" ", name or ""))  # never return empty


def blocking_key(name: str) -> str:
    """Order-independent key. Same key => worth comparing in detail."""
    toks = sorted(set(clean(name).split()))
    return " ".join(toks)


def initials_key(name: str) -> str:
    """Cheap secondary block: first 4 chars of each token, sorted."""
    toks = sorted({t[:4] for t in clean(name).split() if len(t) > 2})
    return "".join(toks)[:24]


def token_set_ratio(a: str, b: str) -> float:
    """Jaccard over token sets. No dependency on rapidfuzz; good enough for blocking."""
    A, B = set(clean(a).split()), set(clean(b).split())
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def score_match(query: str, candidate: str, *, country_match: bool | None = None) -> float:
    """0-1 confidence.

    Country agreement is a tiebreaker, deliberately NOT a veto. Legal domicile
    and operating headquarters routinely disagree for exactly the multinationals
    you most want to match - Eaton Corporation plc is Irish-domiciled with its
    operational HQ in Ohio - so a mismatch nudges the score rather than sinking
    a name match that is otherwise perfect.
    """
    base = token_set_ratio(query, candidate)
    qc, cc = clean(query), clean(candidate)
    exact = bool(qc) and qc == cc
    if exact:
        base = 1.0
    elif qc and cc and (qc.startswith(cc) or cc.startswith(qc)):
        base = max(base, 0.90)
    if country_match is True:
        base = min(1.0, base + 0.05)
    elif country_match is False:
        # Cap the damage, and never let it demote an exact name match out of
        # contention - surface it as a candidate and let the ambiguity rule decide.
        base = max(base * 0.92, 0.86) if exact else base * 0.85
    return round(base, 4)


# --------------------------------------------------------------- countries --
# Registry data carries ISO-2 codes; operational lists carry English names.
# Comparing the two raw is a silent always-false, so both go through here.
_ISO2 = {
    "united states": "US",
    "usa": "US",
    "u s a": "US",
    "america": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
    "netherlands": "NL",
    "holland": "NL",
    "belgium": "BE",
    "luxembourg": "LU",
    "ireland": "IE",
    "switzerland": "CH",
    "austria": "AT",
    "portugal": "PT",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "poland": "PL",
    "czech republic": "CZ",
    "czechia": "CZ",
    "slovakia": "SK",
    "hungary": "HU",
    "romania": "RO",
    "bulgaria": "BG",
    "greece": "GR",
    "turkey": "TR",
    "turkiye": "TR",
    "russia": "RU",
    "ukraine": "UA",
    "china": "CN",
    "hong kong": "HK",
    "macao": "MO",
    "macau": "MO",
    "taiwan": "TW",
    "japan": "JP",
    "south korea": "KR",
    "korea": "KR",
    "india": "IN",
    "indonesia": "ID",
    "malaysia": "MY",
    "singapore": "SG",
    "thailand": "TH",
    "vietnam": "VN",
    "philippines": "PH",
    "australia": "AU",
    "new zealand": "NZ",
    "canada": "CA",
    "mexico": "MX",
    "brazil": "BR",
    "brasil": "BR",
    "argentina": "AR",
    "chile": "CL",
    "colombia": "CO",
    "peru": "PE",
    "south africa": "ZA",
    "egypt": "EG",
    "morocco": "MA",
    "nigeria": "NG",
    "kenya": "KE",
    "israel": "IL",
    "saudi arabia": "SA",
    "united arab emirates": "AE",
    "uae": "AE",
    "qatar": "QA",
    "pakistan": "PK",
    "bangladesh": "BD",
    "sri lanka": "LK",
    "slovenia": "SI",
    "croatia": "HR",
    "serbia": "RS",
    "estonia": "EE",
    "latvia": "LV",
    "lithuania": "LT",
}


def iso2(country: str | None) -> str | None:
    """'United States' -> 'US'; 'US' -> 'US'; unknown -> None (never a guess)."""
    if not country:
        return None
    c = _fold(country)
    if len(c) == 2:
        return c.upper()
    return _ISO2.get(c)


def extract_legal_forms(name: str) -> list[str]:
    """The legal-form tokens present in a name, in order of appearance.

    clean() strips these because they are noise for MATCHING. They are the
    opposite of noise for VALIDATION: a legal form is a registration fact, so
    knowing a name carries "GmbH" tells you a German-speaking registrar created
    the entity. This is the accessor that makes that checkable.
    """
    s = _PAREN_RE.sub(" ", name or "")
    s = _fold(s)
    found, seen = [], set()
    for m in _FORM_RE.finditer(s):
        tok = m.group(1).replace(" ", "")
        if tok and tok not in seen:
            seen.add(tok)
            found.append(tok)
    return found
