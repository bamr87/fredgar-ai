"""Modelled revenue for the records that file nothing public.

Most of any real supplier list is private companies. They have no XBRL, no
filings, and no revenue anyone can cite — but a vendor master still has to
classify spend and size a counterparty, so the number gets estimated. The only
question is whether the estimate is auditable.

    revenue ≈ employees × revenue_per_employee(sector, country)

The original framework hard-coded that benchmark with, in its own words,
"order-of-magnitude placeholders". This version derives it from the filers in
the list itself: ``edgar_facts`` supplies reported revenue and headcount for
every SEC registrant among the records, and the median ratio within a SIC group
becomes the benchmark for the private companies in that same group.

That matters for three reasons. The benchmark comes from the same population it
is applied to rather than from a national average. Its sample size travels with
every estimate, so a reader can see a group of six filers is thinner evidence
than a group of sixty. And it is reproducible — re-run it after syncing more
filers and the number moves, visibly, for a reason.

Every estimate is written unverified with ``revenue_basis='estimated'`` and a
method string naming the benchmark, its sample and its fallback tier. Reported
and estimated are never blended.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any

from ..core.model import Claim, Evidence
from ..core.provider import BaseProvider, Cost
from ..normalize import _fold, iso2

logger = logging.getLogger(__name__)

# Fallback revenue per employee, in USD, when the list contains too few filers in
# a sector to derive one. Order-of-magnitude only, and labelled as such in the
# method string so nobody mistakes it for a measurement.
FALLBACK_RPE = {
    "automotive": 420_000,
    "electronics": 380_000,
    "industrial": 310_000,
    "food and beverage": 340_000,
    "life sciences": 450_000,
    "consumer products": 330_000,
}
DEFAULT_RPE = 300_000

# Wage-cost / purchasing-power adjustment. A plant in Vietnam and one in Germany
# do not convert headcount into revenue at the same rate.
COUNTRY_FACTOR = {
    "US": 1.00,
    "CA": 0.95,
    "GB": 0.92,
    "DE": 0.95,
    "FR": 0.90,
    "IT": 0.85,
    "NL": 0.98,
    "SE": 0.95,
    "CH": 1.10,
    "JP": 0.88,
    "KR": 0.80,
    "AU": 0.95,
    "CN": 0.45,
    "IN": 0.28,
    "ID": 0.25,
    "VN": 0.22,
    "TH": 0.32,
    "MY": 0.40,
    "MX": 0.42,
    "BR": 0.45,
    "PL": 0.55,
    "CZ": 0.58,
    "TR": 0.38,
    "ZA": 0.45,
}
DEFAULT_FACTOR = 0.60

# Median employees per manufacturing site, used only when headcount is unknown.
# The weakest link in the chain, and the confidence below reflects that.
EMPLOYEES_PER_SITE = 180

# Below this, a SIC group's median says more about its outliers than its sector.
MIN_SAMPLE = 5


class RevenueModel(BaseProvider):
    """Estimate revenue from headcount, benchmarked against the list's own filers."""

    name = "revenue_model"
    requires = frozenset({"name"})
    provides = frozenset({"revenue_estimated", "revenue_method", "employees_modelled"})
    cost = Cost.FREE
    needs_prepare = True

    # Every source that could report a real revenue, headcount or SIC. The model
    # is the last resort, not the first guess, so it waits for all of them.
    defer_to = frozenset({"edgar_issuer", "edgar_submissions", "edgar_facts"})

    def prepare(self, ctx) -> None:
        if "rpe_benchmark" not in ctx.shared:
            ctx.shared["rpe_benchmark"] = build_rpe_benchmark(ctx.shared.get("dataset"))

    def eligible(self, rec) -> bool:
        # A filed number is not to be improved upon by a model. Tested against
        # None, not for truthiness: a genuine reported revenue of 0 is a fact
        # about the company, and `if value` silently treats it as missing.
        if rec.get("revenue_reported") is not None:
            return False
        return super().eligible(rec)

    def run(self, rec, ctx):
        benchmark: dict[str, Any] = (ctx.shared or {}).get("rpe_benchmark") or {}

        heads = _to_int(rec.get("employees"))
        if heads:
            head_conf, head_basis = 0.55, "employees=reported"
        else:
            sites = _to_int(rec.get("n_sites")) or 1
            heads = sites * EMPLOYEES_PER_SITE
            head_conf, head_basis = 0.25, f"employees={sites}sites*{EMPLOYEES_PER_SITE}"
            yield Claim(
                "employees_modelled",
                heads,
                0.25,
                self.name,
                Evidence(locator=f"model:employees_per_site={EMPLOYEES_PER_SITE}"),
            )
        if heads <= 0:
            return

        rpe, tier, sample = _lookup_rpe(benchmark, rec)
        country = rec.get("geo_iso2") or iso2(rec.get("country"))
        factor = COUNTRY_FACTOR.get(country or "", DEFAULT_FACTOR)

        # The benchmark tier caps confidence: a derived median over sixty filers
        # is evidence, a national placeholder is an order of magnitude.
        tier_conf = {"sic4": 1.0, "sic2": 0.85, "all_filers": 0.6, "fallback": 0.4}[tier]
        confidence = round(head_conf * tier_conf, 3)

        method = (
            f"rev_per_head_v2[rpe={rpe:,.0f};tier={tier};n={sample};"
            f"country={country or '??'};factor={factor};{head_basis}]"
        )
        ev = Evidence(
            locator=f"model:{tier}",
            snippet=(
                f"{heads:,} employees x {rpe:,.0f} USD/employee x {factor} "
                f"({tier} benchmark, n={sample})"
            ),
        )
        yield Claim("revenue_estimated", round(heads * rpe * factor, 2), confidence, self.name, ev)
        yield Claim("revenue_method", method, confidence, self.name, ev)


def _lookup_rpe(benchmark: dict[str, Any], rec) -> tuple[float, str, int]:
    """Best available revenue-per-employee for this record: (value, tier, sample).

    Narrowest evidence first — the company's own 4-digit SIC, then its 2-digit
    division, then every filer in the list, then the static table.
    """
    sic = str(rec.get("sic") or "").strip()
    by_sic4 = benchmark.get("sic4") or {}
    by_sic2 = benchmark.get("sic2") or {}

    if sic and sic in by_sic4:
        return by_sic4[sic]["rpe"], "sic4", by_sic4[sic]["n"]
    if sic and sic[:2] in by_sic2:
        return by_sic2[sic[:2]]["rpe"], "sic2", by_sic2[sic[:2]]["n"]

    overall = benchmark.get("all_filers")
    if overall and overall["n"] >= MIN_SAMPLE:
        return overall["rpe"], "all_filers", overall["n"]

    verticals = rec.get("vertical") or []
    if isinstance(verticals, str):
        verticals = [verticals]
    for v in verticals:
        hit = FALLBACK_RPE.get(_fold(str(v)))
        if hit:
            return float(hit), "fallback", 0
    return float(DEFAULT_RPE), "fallback", 0


def build_rpe_benchmark(dataset=None) -> dict[str, Any]:
    """Median revenue-per-employee by SIC, from the filers this pipeline resolved.

    Reads ``edgar_facts`` and ``edgar_submissions`` claims directly rather than
    golden fields, so a benchmark is available without an intervening resolve —
    and, more importantly, so it can only ever be built from filings. Reading
    golden would let a previous run's *estimates* feed the benchmark that
    produces the next run's estimates, which is a model training on its own
    output.

    Restricted to one dataset when given, since a benchmark drawn from a
    different list is exactly the national-average problem this replaces.

    Median rather than mean: one refinery among forty machine shops would
    otherwise move the benchmark for all of them.

    A benchmark is only as good as the EDGAR pass behind it. On a dataset whose
    SEC providers have not run, this returns empty and every estimate falls back
    to the static table — visibly, as ``tier=fallback`` in the method string.
    """
    from warehouse.models import EnrichmentClaim

    qs = EnrichmentClaim.objects.filter(
        provider__in=("edgar_facts", "edgar_submissions"),
        field__in=("revenue_reported", "employees", "sic"),
        verified=True,
    )
    if dataset is not None:
        qs = qs.filter(record__dataset=dataset)

    per_record: dict[int, dict[str, Any]] = {}
    for record_id, field, value in qs.values_list("record_id", "field", "value"):
        per_record.setdefault(record_id, {})[field] = value

    ratios_by_sic4: dict[str, list[float]] = {}
    ratios_by_sic2: dict[str, list[float]] = {}
    all_ratios: list[float] = []

    for row in per_record.values():
        revenue = _to_float(row.get("revenue_reported"))
        employees = _to_int(row.get("employees"))
        if not revenue or not employees or revenue <= 0 or employees <= 0:
            continue
        ratio = revenue / employees
        # A ratio outside this band is a unit error or a holding company with no
        # staff, not a sector signal.
        if not (10_000 <= ratio <= 10_000_000):
            continue
        all_ratios.append(ratio)
        sic = str(row.get("sic") or "").strip()
        if sic:
            ratios_by_sic4.setdefault(sic, []).append(ratio)
            ratios_by_sic2.setdefault(sic[:2], []).append(ratio)

    def summarize(groups: dict[str, list[float]]) -> dict[str, dict[str, Any]]:
        return {
            key: {"rpe": statistics.median(values), "n": len(values)}
            for key, values in groups.items()
            if len(values) >= MIN_SAMPLE
        }

    benchmark = {
        "sic4": summarize(ratios_by_sic4),
        "sic2": summarize(ratios_by_sic2),
        "all_filers": (
            {"rpe": statistics.median(all_ratios), "n": len(all_ratios)} if all_ratios else None
        ),
    }
    logger.info(
        "Revenue benchmark: %s filers, %s SIC-4 groups, %s SIC-2 groups",
        len(all_ratios),
        len(benchmark["sic4"]),
        len(benchmark["sic2"]),
    )
    return benchmark


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
