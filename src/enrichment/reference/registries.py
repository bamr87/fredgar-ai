"""What a legal form implies about jurisdiction, and which register to query.

The tables live in ``data/reference/enrichment/business_registries.json``; this
module is the logic that reads them.

REGISTRIES
    The authoritative company register per jurisdiction, its GLEIF Registration
    Authority code, and whether it is freely queryable. GLEIF Level 1 records
    carry ``registeredAt`` (an RA code) and ``registeredAs`` (the local
    registration number), which is what bridges an LEI to a national entry.

LEGAL_FORM_JURISDICTION
    A legal form is a *registration fact*. "GmbH" exists because a German,
    Austrian or Swiss registrar created it. So a record whose legal form and
    stated country disagree is either a subsidiary naming convention, a data
    error, or a genuinely cross-border entity — and all three are worth flagging
    before anyone pays an invoice against it.
"""

from __future__ import annotations

from functools import lru_cache

from .loader import business_registries


@lru_cache(maxsize=1)
def _forms() -> dict[str, frozenset[str]]:
    raw = business_registries()["legal_form_jurisdiction"]
    return {k: frozenset(v) for k, v in raw.items()}


@lru_cache(maxsize=1)
def _ambiguous() -> frozenset[str]:
    return frozenset(business_registries()["ambiguous_forms"])


@lru_cache(maxsize=1)
def _sorted_form_keys() -> tuple[str, ...]:
    return tuple(sorted((k for k in _forms() if len(k) >= 2), key=len, reverse=True))


def _decompose(token: str) -> list[str]:
    """Greedy longest-match split of a folded composite into known sub-forms."""
    keys = _sorted_form_keys()
    parts: list[str] = []
    i = 0
    while i < len(token):
        for k in keys:
            if token.startswith(k, i):
                parts.append(k)
                i += len(k)
                break
        else:
            i += 1
    return parts


def is_ambiguous(form_token: str) -> bool:
    """True when a form carries no reliable jurisdiction signal.

    An EXACT key in the table is judged on its own merits — "sarl" is a real,
    specific form even though it happens to begin with the ambiguous "sa". Only
    tokens absent from the table are decomposed, and such a token is ambiguous
    when every root it resolves to is ("corporation" -> "corp").

    Prefix-matching the raw token against short ambiguous roots was wrong: it
    condemned "sarl", "sdnbhd" and every other legitimate form starting with two
    ambiguous letters.
    """
    t = (form_token or "").lower()
    if not t:
        return True
    if t in _forms():
        return t in _ambiguous()
    parts = _decompose(t)
    return (not parts) or all(p in _ambiguous() for p in parts)


def registry_for(iso2_code: str | None) -> dict:
    """The authoritative register for a jurisdiction, GLEIF as the fallback."""
    data = business_registries()
    registries = data["registries"]
    if iso2_code and iso2_code.upper() in registries:
        out = dict(registries[iso2_code.upper()])
        out["scope"] = "national"
        return out
    out = dict(data["global_registry"])
    out["scope"] = "global"
    return out


def jurisdictions_for_form(form_token: str) -> set[str]:
    """Jurisdictions that can create this form.

    Composite forms fold into one token once punctuation is removed, so an exact
    lookup is tried first, then a decomposition into the longest known sub-forms.
    "sdnbhd" resolves via the composite key; an unseen composite like "srlcv"
    still resolves through its parts — intersected, since a composite must be
    creatable in a jurisdiction that allows all of its parts.
    """
    t = (form_token or "").lower()
    if not t:
        return set()
    forms = _forms()
    if t in forms:
        return set(forms[t])

    parts = _decompose(t)
    if not parts:
        return set()
    out: set[str] | None = None
    for part in parts:
        j = set(forms[part])
        out = j if out is None else (out & j)
    return out or set()
