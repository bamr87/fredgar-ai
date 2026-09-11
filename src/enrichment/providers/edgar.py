"""SEC EDGAR as an enrichment source.

This is where the framework stops being generic and starts being fredgar. Three
providers, ordered so the free one runs first and the paid ones only fire on
rows it resolved:

``edgar_issuer`` (bulk, offline)
    Blocks the input list against ``ListedIssuer`` — SEC's own
    ``company_tickers.json``, already cached in the warehouse — to find each
    row's CIK. No network at all: one dictionary lookup per record.

``edgar_submissions`` (api, database-first)
    SEC's entity record for that filer: legal name, SIC, business address,
    phone, EIN, state of incorporation, former names, listings.

``edgar_facts`` (api, database-first)
    What the company filed about itself in XBRL: revenue, employees, net income,
    total assets. These are the only *reported* financials the pipeline will ever
    see, which is what makes ``revenue_basis`` mean something.

Both API providers read through ``sec_edgar.services.edgar_sec_payload``, so a
payload already in the database is reused and SEC is never called twice for the
same entity. That is not an optimisation — SEC enforces fair-access limits, and
an enrichment run over ten thousand names is exactly the shape of traffic they
throttle.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from sec_edgar.cik import normalize_cik
from sec_edgar.reference_data import concept_groups_ordered

from ..core.model import Claim, Evidence
from ..core.provider import BaseProvider, Cost
from ..normalize import blocking_key, clean, score_match
from .geo import resolve_country

logger = logging.getLogger(__name__)

EDGAR_ENTITY_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Concepts carrying a headcount. SEC moved employee counts into dei with the
# cover-page taxonomy; older filers used the us-gaap tag.
EMPLOYEE_CONCEPTS = ("EntityNumberOfEmployees", "NumberOfEmployees")

# Non-revenue figures worth carrying into a vendor master: they size the
# counterparty. Ordered by preference within each field.
BALANCE_CONCEPTS = {
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "total_assets": ("Assets",),
    "stockholders_equity": ("StockholdersEquity",),
}


class EdgarIssuerMatch(BaseProvider):
    """Find each record's SEC CIK by blocking against the cached issuer catalogue.

    Free and offline: ``ListedIssuer`` is SEC's ``company_tickers.json``
    materialised in the warehouse, so this is a dictionary lookup, not a request.
    Running it first means the expensive SEC providers only fire on rows that
    actually correspond to a filer — for a manufacturing supplier list that is a
    small minority, and paying per-row to discover that would be absurd.

    The match is deliberately conservative, for the reason the website verifier
    is: a wrong CIK does not fail loudly, it silently attaches another company's
    audited financials to this record. Two guards enforce that:

    * An exact normalised-name match verifies. Anything else is a proposal.
    * A near-tie between two different CIKs verifies *neither* and records why.
      "Delta Corp" honestly matches several filers, and picking the
      alphabetically-first one is not a decision anyone would defend.
    """

    name = "edgar_issuer"
    requires = frozenset({"blocking_key"})
    provides = frozenset({"cik", "ticker", "edgar_name", "legal_name"})
    cost = Cost.BULK
    needs_prepare = True
    threshold = 0.88
    # A rival within this much of the winner makes the match ambiguous, not close.
    tie_margin = 0.03

    def prepare(self, ctx) -> None:
        if "edgar_issuer_index" in ctx.shared:
            return
        ctx.shared["edgar_issuer_index"] = build_issuer_index()

    def run(self, rec, ctx):
        index = (ctx.shared or {}).get("edgar_issuer_index") or {}
        candidates = index.get(rec.get("blocking_key")) or []
        if not candidates:
            return

        scored = sorted(
            ((score_match(rec.get("name") or "", c["name"]), c) for c in candidates),
            key=lambda pair: pair[0],
            reverse=True,
        )
        best_score, best = scored[0]
        if best_score < self.threshold:
            return

        rivals = [
            c
            for s, c in scored[1:]
            if c["cik"] != best["cik"] and (best_score - s) <= self.tie_margin
        ]
        url = EDGAR_ENTITY_URL.format(cik=best["cik"])
        ev = Evidence(
            url=url,
            locator="company_tickers.json",
            snippet=f"{best['name']} (CIK {best['cik']}, ticker {best['ticker'] or '—'})",
        )

        if rivals:
            # Several filers answer to this name. Say so instead of choosing.
            names = ", ".join(f"{c['name']} [{c['cik']}]" for c in rivals[:3])
            yield Claim("cik", best["cik"], round(best_score * 0.5, 4), self.name, ev)
            yield Claim(
                "validation_reason",
                f"edgar_ambiguous_name:{len(rivals) + 1}_filers_match({names})",
                0.9,
                self.name,
                ev,
            )
            return

        exact = clean(rec.get("name") or "") == clean(best["name"])
        yield Claim("cik", best["cik"], best_score, self.name, ev, verified=exact)
        yield Claim("edgar_name", best["name"], best_score, self.name, ev, verified=exact)
        yield Claim("legal_name", best["name"], best_score, self.name, ev, verified=exact)
        if best["ticker"]:
            yield Claim("ticker", best["ticker"].upper(), best_score, self.name, ev, verified=exact)


def build_issuer_index() -> dict[str, list[dict[str, Any]]]:
    """Index every cached ``ListedIssuer`` by blocking key. One pass, no network.

    Returns ``{blocking_key: [{cik, ticker, name}, …]}``. Built once per run and
    handed to providers through ``ctx.shared``; a few tens of thousands of rows
    cost a few megabytes and save one request per record.
    """
    from warehouse.models import ListedIssuer

    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = ListedIssuer.objects.all().values_list("cik", "ticker", "name")
    for cik, ticker, name in rows.iterator(chunk_size=5000):
        if not name:
            continue
        index[blocking_key(name)].append({"cik": cik, "ticker": ticker, "name": name})
    logger.info("Built EDGAR issuer index: %s blocking keys", len(index))
    return dict(index)


def identity_confidence(rec) -> tuple[bool, float]:
    """How well established is this record's CIK? (verified, confidence).

    Everything the SEC providers emit is derived from this one identity, so
    nothing they emit may outrank it. Stamping XBRL ``verified=True`` because "a
    filer signed it" is only true if the filer is the right one — on an
    unverified CIK it is the Eaton Vance bug in a new costume, with a citable
    data.sec.gov URL instead of a citable homepage.

    Falls back to trusting a CIK that came in on the seed: if the input list
    supplied it, its accuracy is the list's business, not this pipeline's.
    """
    claims = rec.claims_for("cik")
    if not claims:
        return True, 1.0  # seeded CIK — the list asserted it
    best = max(claims, key=lambda c: (c.verified, c.confidence))
    return best.verified, best.confidence


class EdgarSubmissions(BaseProvider):
    """SEC's entity record for a filer — database-first, then data.sec.gov.

    Everything here is what the registrant told SEC about itself, which puts it
    above anything a website or a heuristic can offer. Note the two addresses:
    SEC carries a business address and a mailing address, and only the first is
    a place where the company does anything.
    """

    name = "edgar_submissions"
    requires = frozenset({"cik"})
    provides = frozenset(
        {
            "legal_name",
            "sic",
            "sic_description",
            "industry",
            "hq_city",
            "hq_region_raw",
            "hq_postal",
            "hq_country_site",
            "hq_street",
            "phone",
            "ein",
            "state_of_incorporation",
            "entity_type",
            "fiscal_year_end",
            "exchange",
            "alias",
            "entity_status",
        }
    )
    cost = Cost.API
    rate_per_sec = 8.0

    def run(self, rec, ctx):
        from sec_edgar.services.edgar_sec_payload import get_submissions_payload

        cik = normalize_cik(str(rec.get("cik")))
        payload = get_submissions_payload(cik, user_agent_email=ctx.user_agent_email)
        if not payload:
            return

        # No claim here can be better established than the CIK it came from.
        sure, identity = identity_confidence(rec)
        scale = 1.0 if sure else identity

        url = SUBMISSIONS_URL.format(cik=cik)
        ev = Evidence(
            url=url, locator="sec_submissions", snippet=str(payload.get("name") or "")[:200]
        )
        if not sure:
            yield Claim(
                "validation_reason",
                f"sec_data_on_unverified_cik:{cik}@{identity:.2f}",
                0.9,
                self.name,
                ev,
            )

        if payload.get("name"):
            yield Claim("legal_name", payload["name"], 0.97 * scale, self.name, ev, verified=sure)
        if payload.get("sic"):
            yield Claim("sic", str(payload["sic"]), 0.97 * scale, self.name, ev, verified=sure)
        if payload.get("sicDescription"):
            yield Claim(
                "sic_description",
                payload["sicDescription"],
                0.97 * scale,
                self.name,
                ev,
                verified=sure,
            )
            yield Claim("industry", payload["sicDescription"], 0.9 * scale, self.name, ev)

        for field, key, confidence in (
            ("ein", "ein", 0.95),
            ("state_of_incorporation", "stateOfIncorporation", 0.95),
            ("entity_type", "entityType", 0.9),
            ("fiscal_year_end", "fiscalYearEnd", 0.9),
            ("phone", "phone", 0.9),
        ):
            value = payload.get(key)
            if value:
                yield Claim(field, str(value).strip(), confidence * scale, self.name, ev)

        # The business address, not the mailing address: a lockbox in Delaware is
        # not a location, and treating it as one is how vendor masters end up
        # claiming a factory in a PO box.
        addr = (payload.get("addresses") or {}).get("business") or {}
        for field, key, confidence in (
            ("hq_city", "city", 0.93),
            ("hq_postal", "zipCode", 0.9),
            ("hq_street", "street1", 0.9),
        ):
            value = addr.get(key)
            if value and str(value).strip():
                yield Claim(field, str(value).strip(), confidence * scale, self.name, ev)

        # SEC packs state and country into one field. `stateOrCountry` is an
        # internal code ("L2" for Ireland) that means nothing downstream, and
        # `stateOrCountryDescription` is a US state name for domestic filers and a
        # COUNTRY name for foreign ones. Feeding "Ireland" to a US subdivision
        # matcher is how a country ends up filed as a province — so resolve it
        # first and emit whichever thing it actually is.
        region_or_country = str(addr.get("stateOrCountryDescription") or "").strip()
        if region_or_country:
            country_code = resolve_country(region_or_country)
            if country_code:
                yield Claim(
                    "hq_country_site", country_code, 0.93 * scale, self.name, ev, verified=sure
                )
            else:
                yield Claim("hq_region_raw", region_or_country, 0.9 * scale, self.name, ev)

        for exch, ticker in zip(payload.get("exchanges") or [], payload.get("tickers") or []):
            if exch:
                yield Claim(
                    "exchange", {"exchange": exch, "ticker": ticker}, 0.95 * scale, self.name, ev
                )

        # Former names are the aliases that make a CRM row match next time.
        for former in (payload.get("formerNames") or [])[:8]:
            former_name = (former or {}).get("name")
            if former_name:
                yield Claim(
                    "alias",
                    former_name,
                    0.9 * scale,
                    self.name,
                    Evidence(url=url, locator="sec_submissions:formerNames"),
                )


class EdgarFacts(BaseProvider):
    """Reported financials from XBRL company facts — database-first, then SEC.

    The one provider in the pipeline that produces *reported* rather than
    modelled numbers. Everything it emits is verified, because a filer signed it.

    Annual figures only, and the frame matters: ``fy``/``fp`` pin a value to a
    fiscal year, and duration facts (revenue, income) are taken from the longest
    period ending latest so a quarter never masquerades as a year.
    """

    name = "edgar_facts"
    requires = frozenset({"cik"})
    provides = frozenset(
        {
            "revenue_reported",
            "revenue_period_end",
            "revenue_currency",
            "employees",
            "net_income",
            "total_assets",
            "stockholders_equity",
        }
    )
    cost = Cost.API
    rate_per_sec = 8.0

    def run(self, rec, ctx):
        from sec_edgar.services.edgar_sec_payload import get_company_facts_payload

        cik = normalize_cik(str(rec.get("cik")))
        try:
            payload = get_company_facts_payload(cik, user_agent_email=ctx.user_agent_email)
        except Exception as exc:
            if not _is_not_found(exc):
                raise
            # A filer with no XBRL is not a failure, it is a finding: foreign
            # private issuers (Rio Tinto, Daikin, Fresenius) file on forms that
            # carry no companyfacts endpoint, so their revenue has to be
            # modelled like any private company's. Recording that keeps nine
            # legitimate outcomes out of the error count, where they looked like
            # a broken provider.
            yield Claim(
                "validation_reason",
                f"no_xbrl_company_facts:{cik}",
                0.9,
                self.name,
                Evidence(url=COMPANY_FACTS_URL.format(cik=cik), locator="sec_404"),
            )
            return

        facts = (payload or {}).get("facts") or {}
        if not facts:
            return

        # Filed financials are only as trustworthy as the identity they hang on.
        sure, identity = identity_confidence(rec)
        scale = 1.0 if sure else identity

        url = COMPANY_FACTS_URL.format(cik=cik)

        revenue_concepts = concept_groups_ordered().get("revenue", ("Revenues",))
        rev = _latest_annual(facts, "us-gaap", revenue_concepts, duration=True)
        if rev:
            ev = Evidence(
                url=url,
                locator=f"xbrl:us-gaap:{rev['concept']}:{rev['frame']}",
                snippet=f"{rev['concept']} {rev['value']:,.0f} {rev['unit']} "
                f"for FY{rev['fy']} ending {rev['end']}",
            )
            yield Claim(
                "revenue_reported", float(rev["value"]), 0.97 * scale, self.name, ev, verified=sure
            )
            yield Claim(
                "revenue_period_end", rev["end"], 0.97 * scale, self.name, ev, verified=sure
            )
            yield Claim("revenue_currency", rev["unit"], 0.97 * scale, self.name, ev, verified=sure)

        heads = _latest_annual(facts, "dei", EMPLOYEE_CONCEPTS, duration=False)
        if heads:
            ev = Evidence(
                url=url,
                locator=f"xbrl:dei:{heads['concept']}:{heads['frame']}",
                snippet=f"{heads['value']:,.0f} employees as of {heads['end']}",
            )
            yield Claim(
                "employees", int(heads["value"]), 0.95 * scale, self.name, ev, verified=sure
            )

        for field, concepts in BALANCE_CONCEPTS.items():
            duration = field == "net_income"
            hit = _latest_annual(facts, "us-gaap", concepts, duration=duration)
            if not hit:
                continue
            ev = Evidence(
                url=url,
                locator=f"xbrl:us-gaap:{hit['concept']}:{hit['frame']}",
                snippet=f"{hit['concept']} {hit['value']:,.0f} {hit['unit']} at {hit['end']}",
            )
            yield Claim(field, float(hit["value"]), 0.95 * scale, self.name, ev, verified=sure)


def _latest_annual(
    facts: dict[str, Any],
    taxonomy: str,
    concepts: tuple[str, ...] | list[str],
    *,
    duration: bool,
) -> dict[str, Any] | None:
    """Most recent annual value across a group of interchangeable concepts.

    ``duration=True`` selects flow facts (revenue, income) and requires a period
    of roughly a year, so a quarter is never mistaken for one. ``duration=False``
    selects instant facts (assets, headcount), which carry no start date.

    Recency decides first, tag preference only breaks ties. Taking the first
    *concept* that had any value instead looked reasonable and was wrong: Eaton
    carries a stray ``Revenues`` series of zeroes for 2015–2016 alongside a real
    ``RevenueFromContractWithCustomerExcludingAssessedTax`` series running to
    2025, and preferring the tag produced a reported revenue of $0 — a verified
    claim, with a citable SEC URL, that was nonsense. Whichever tag a filer
    currently uses is the one carrying the current number.
    """
    taxonomy_facts = facts.get(taxonomy) or {}
    best: dict[str, Any] | None = None

    for rank, concept in enumerate(concepts):
        units = (taxonomy_facts.get(concept) or {}).get("units") or {}
        for unit, entries in units.items():
            for entry in entries:
                if entry.get("form") not in ("10-K", "20-F", "40-F"):
                    continue
                if entry.get("fp") not in (None, "FY"):
                    continue
                end = entry.get("end")
                value = _to_number(entry.get("val"))
                if not end or value is None:
                    continue
                start = entry.get("start")
                if duration:
                    if not start or not _is_annual(start, end):
                        continue
                elif start:
                    continue
                candidate = {
                    "concept": concept,
                    "rank": rank,
                    "value": value,
                    "unit": unit,
                    "end": end,
                    "fy": entry.get("fy"),
                    "frame": entry.get("frame") or f"{entry.get('fy')}{entry.get('fp') or ''}",
                }
                # Later period wins; at the same period, the preferred tag wins.
                if best is None or (candidate["end"], -rank) > (best["end"], -best["rank"]):
                    best = candidate
    return best


def _is_annual(start: str, end: str) -> bool:
    """True for a period of roughly a year (330–400 days), tolerating 52/53-week years."""
    from datetime import date

    try:
        s = date.fromisoformat(start[:10])
        e = date.fromisoformat(end[:10])
    except (ValueError, TypeError):
        return False
    return 330 <= (e - s).days <= 400


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _is_not_found(exc: BaseException) -> bool:
    """True when an exception chain bottoms out in an HTTP 404.

    ``SecEdgarClient`` retries through tenacity, so a 404 arrives wrapped in a
    ``RetryError`` around the last attempt's ``HTTPError``. Unwrapping it here
    rather than catching everything keeps a genuine outage an error.
    """
    seen: set[int] = set()
    stack: list[BaseException | None] = [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))

        response = getattr(current, "response", None)
        if getattr(response, "status_code", None) == 404:
            return True

        last_attempt = getattr(current, "last_attempt", None)  # tenacity.RetryError
        if last_attempt is not None:
            try:
                last_attempt.result()
            except BaseException as inner:  # noqa: BLE001 - inspecting, not handling
                stack.append(inner)
        stack.extend([current.__cause__, current.__context__])
    return False
