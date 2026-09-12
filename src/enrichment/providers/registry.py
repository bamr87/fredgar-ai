"""Validation against public business registers.

Both providers here are free, offline and cover 100% of records.

JurisdictionCheck
    A legal form is a registration fact. "GmbH" exists because a German,
    Austrian or Swiss registrar created it; "Sdn Bhd" because a Malaysian one
    did. So a record whose form and stated country disagree is flagged BEFORE
    any network call - and it also tells you WHICH register to query.

HqInference
    Uses that same registration fact to pick a headquarters out of an
    operational footprint. Never verified: no register has confirmed it.

The actual register lookups are separate providers. For US filers that is
:mod:`enrichment.providers.edgar`, which reads SEC's own entity record; GLEIF
would be the equivalent for the rest of the world and slots in the same way.
"""

from __future__ import annotations

from ..core.model import Claim, Evidence
from ..core.provider import BaseProvider, Cost
from ..normalize import extract_legal_forms
from ..reference.registries import (
    is_ambiguous,
    jurisdictions_for_form,
    registry_for,
)
from .geo import resolve_country


class JurisdictionCheck(BaseProvider):
    """Offline validation: does the legal form agree with the stated country?"""

    name = "jurisdiction"
    requires = frozenset({"name"})
    provides = frozenset(
        {
            "legal_form_token",
            "form_jurisdictions",
            "jurisdiction_check",
            "registry_name",
            "registry_url",
            "registry_ra",
            "registry_free_api",
            "validation_reason",
        }
    )
    cost = Cost.FREE

    def run(self, rec, ctx):
        code = rec.get("geo_iso2") or resolve_country(rec.get("country"))
        reg = registry_for(code)
        ev_reg = Evidence(url=reg.get("url"), locator=f"registry_map:{code or 'global'}")
        yield Claim("registry_name", reg["name"], 1.0, self.name, ev_reg)
        if reg.get("url"):
            yield Claim("registry_url", reg["url"], 1.0, self.name, ev_reg)
        if reg.get("ra"):
            yield Claim("registry_ra", reg["ra"], 1.0, self.name, ev_reg)
        yield Claim("registry_free_api", bool(reg.get("free_api")), 1.0, self.name, ev_reg)

        forms = extract_legal_forms(rec.get("name") or "")
        # Score the most specific (longest) non-ambiguous form present.
        usable = [
            f
            for f in sorted(forms, key=len, reverse=True)
            if not is_ambiguous(f) and jurisdictions_for_form(f)
        ]
        if not usable:
            yield Claim(
                "jurisdiction_check",
                "unknown",
                1.0,
                self.name,
                Evidence(locator=f"forms={forms or 'none'}"),
            )
            return

        tok = usable[0]
        juris = jurisdictions_for_form(tok)
        ev = Evidence(
            locator=f"legal_form:{tok}", snippet=f"{tok} is registrable in {sorted(juris)}"
        )
        yield Claim("legal_form_token", tok, 0.9, self.name, ev)
        yield Claim("form_jurisdictions", sorted(juris), 0.9, self.name, ev)

        if not code:
            yield Claim("jurisdiction_check", "no_country", 1.0, self.name, ev)
            return
        if code in juris:
            yield Claim("jurisdiction_check", "consistent", 0.9, self.name, ev, verified=True)
        else:
            # Not necessarily an error: a German parent's Brazilian plant may be
            # listed under its group name. But it is never nothing.
            yield Claim("jurisdiction_check", "inconsistent", 0.9, self.name, ev)
            yield Claim(
                "validation_reason",
                f"form_country_mismatch:{tok}~{code}(expected {'/'.join(sorted(juris)[:4])})",
                0.9,
                self.name,
                ev,
            )


class HqInference(BaseProvider):
    """Pick the headquarters country using the legal form as evidence.

    An operational list orders countries by site count, not by domicile, so its
    first entry is a guess. But a legal form is a registration fact: if a record
    is a "B.V." and the Netherlands appears anywhere in its footprint, the
    Netherlands is where the registrar that created it sits.

    This is the difference between "Akzo Nobel Nederland BV is in the United
    Kingdom" and a headquarters you can actually query a register with.
    """

    name = "hq_inference"
    requires = frozenset({"countries_iso", "legal_form_token"})
    provides = frozenset({"hq_country_inferred", "hq_inference_basis"})
    cost = Cost.FREE

    def run(self, rec, ctx):
        codes = rec.get("countries_iso") or []
        tok = rec.get("legal_form_token")
        if not codes or not tok or len(codes) < 2:
            return
        juris = jurisdictions_for_form(tok)
        hits = [c for c in codes if c in juris]
        if len(hits) != 1:
            return  # ambiguous or absent - say nothing
        code = hits[0]
        if code == codes[0]:
            return  # already the working guess; no news

        # Confidence scales with how SPECIFIC the form is. "GmbH" narrows to
        # five German-speaking jurisdictions; "plc" spans seven across two
        # continents, and picking the single one that happens to appear in a
        # footprint is a weaker argument. Eaton Corporation plc is Irish-
        # domiciled but has no Irish site listed, so this rule proposes GB -
        # a better answer than "United States", still not the right one.
        conf = 0.85 if len(juris) <= 3 else (0.70 if len(juris) <= 5 else 0.55)
        ev = Evidence(
            locator=f"legal_form:{tok}",
            snippet=f"{tok} is registrable in {sorted(juris)[:5]}; "
            f"{code} is the only one in footprint {codes[:6]}",
        )
        # NEVER verified: no register has confirmed this. It is a defensible
        # inference from a registration fact, and the golden resolver must be
        # free to let any real registry lookup outrank it.
        yield Claim("hq_country_inferred", code, conf, self.name, ev, verified=False)
        yield Claim(
            "hq_inference_basis",
            f"legal_form:{tok};jurisdictions={len(juris)};first_listed_was:{codes[0]}",
            conf,
            self.name,
            ev,
        )
