"""FRED as macro context for an enriched party record.

EDGAR says what one company reported. FRED says what its sector and its price
level were doing at the time. Two providers join them:

``fred_macro``
    Links each record to the FRED series that govern its sector, using the
    ``industries`` tags already curated in ``public_data/bundles/*.json``. Free
    and offline — the bundles are committed, and observations come from the
    warehouse if they have been synced.

``fred_deflator``
    Converts a *reported* revenue (from ``edgar_facts``, with the fiscal period
    it belongs to) into constant dollars. Comparing a vendor's FY2019 revenue
    against another's FY2024 without this is comparing two different dollars,
    and a vendor master that ranks spend by nominal figures will rank it wrong.

Both degrade to silence rather than to a guess: with no FRED observations in the
database, ``fred_deflator`` emits nothing at all. FRED is also overwhelmingly a
US statistical system, so every macro claim carries an explicit scope — attaching
US industrial production to a Malaysian supplier without saying so would be the
macro equivalent of an unverified website.
"""

from __future__ import annotations

import functools
import json
import logging
from pathlib import Path
from typing import Any

from ..core.model import Claim, Evidence
from ..core.provider import BaseProvider, Cost
from ..normalize import _fold

logger = logging.getLogger(__name__)

FRED_SERIES_URL = "https://fred.stlouisfed.org/series/{series_id}"

# Where a list's own vertical language lands in the curated bundles. Anything not
# named here still routes through the bundles' `industries` tags below.
VERTICAL_BUNDLES = {
    "industrial": ("manufacturing",),
    "industrials": ("manufacturing",),
    "manufacturing": ("manufacturing",),
    "automotive": ("autos",),
    "autos": ("autos",),
    "electronics": ("technology",),
    "technology": ("technology",),
    "semiconductors": ("technology",),
    "consumer products": ("consumer",),
    "consumer": ("consumer",),
    "food and beverage": ("consumer",),
    "food beverage": ("consumer",),
    "life sciences": ("healthcare",),
    "healthcare": ("healthcare",),
    "pharmaceuticals": ("healthcare",),
    "chemicals": ("materials",),
    "materials": ("materials",),
    "metals": ("materials",),
    "energy": ("energy",),
    "oil and gas": ("energy",),
    "transportation": ("transportation",),
    "logistics": ("transportation",),
    "aerospace": ("manufacturing",),
    "construction": ("housing",),
    "financial services": ("financials",),
}

# SIC prefix -> bundle, longest prefix wins. Preferred over a list's own vertical
# tags because SIC is what the registrant told SEC it *does*, whereas a supplier
# list's verticals describe who it sells to. Eaton is tagged
# "Automotive|Consumer Products|Electronics|Industrial|Life Sciences" — five end
# markets, alphabetically — while its SIC 3590 says industrial machinery, which
# is the thing whose output index actually moves with its revenue.
SIC_BUNDLES = {
    "15": "housing",
    "16": "housing",
    "17": "housing",
    "20": "consumer",  # food & kindred products
    "21": "consumer",
    "22": "consumer",
    "23": "consumer",
    "24": "housing",
    "25": "consumer",
    "26": "materials",
    "28": "materials",  # chemicals
    "283": "healthcare",  # drugs
    "29": "energy",  # petroleum refining
    "30": "materials",
    "31": "consumer",
    "32": "materials",
    "33": "materials",
    "34": "manufacturing",
    "35": "manufacturing",
    "357": "technology",  # computer equipment
    "36": "technology",  # electronic equipment
    "371": "autos",  # motor vehicles
    "372": "manufacturing",
    "373": "manufacturing",
    "38": "manufacturing",
    "384": "healthcare",  # medical instruments
    "39": "manufacturing",
    "40": "transportation",
    "42": "transportation",
    "44": "transportation",
    "45": "transportation",
    "47": "transportation",
    "48": "technology",
    "49": "energy",
    "50": "manufacturing",
    "51": "consumer",
    "52": "consumer",
    "53": "consumer",
    "54": "consumer",
    "55": "consumer",
    "56": "consumer",
    "57": "consumer",
    "58": "consumer",
    "59": "consumer",
    "60": "financials",
    "61": "financials",
    "62": "financials",
    "63": "financials",
    "64": "financials",
    "65": "housing",
    "67": "financials",
    "73": "technology",
    "80": "healthcare",
    "87": "technology",
}

# A goods producer with no usable vertical still sits in the goods economy.
FALLBACK_BUNDLE = "manufacturing"


def bundle_for_sic(sic: str | None) -> str | None:
    """Bundle implied by a SIC code, most specific prefix first."""
    code = str(sic or "").strip()
    for length in (3, 2):
        hit = SIC_BUNDLES.get(code[:length])
        if hit:
            return hit
    return None


# Series that price a sector's own output, preferred over headline CPI because
# they deflate what the company actually sells. First match wins.
DEFLATORS = {
    "manufacturing": "PCUOMFGOMFG",  # PPI: total manufacturing industries
    "materials": "WPU101",  # PPI: iron and steel
    "energy": "WPU0561",  # PPI: crude petroleum
    "transportation": "WPU3012",  # PPI: truck transportation
}
DEFAULT_DEFLATOR = "CPIAUCSL"  # headline CPI, when nothing sector-specific fits

# How much context to attach per record. The point is context, not a data dump;
# the bundle page carries the rest. A supplier list row routinely carries five
# verticals ("Industrial|Automotive|Consumer Products|Electronics|Life Sciences")
# because it sells into all of them — attaching a bundle per vertical buried the
# one describing what the company makes under five describing its customers.
MAX_BUNDLES_PER_RECORD = 2
MAX_SERIES_PER_RECORD = 6


def _bundle_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "public_data" / "bundles"


@functools.lru_cache(maxsize=1)
def load_bundles() -> dict[str, dict[str, Any]]:
    """Every committed FRED bundle, by slug. Read once per process."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(_bundle_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):  # pragma: no cover - bad committed file
            logger.warning("Skipping unreadable FRED bundle %s", path)
            continue
        if data.get("slug"):
            out[data["slug"]] = data
    return out


@functools.lru_cache(maxsize=1)
def _industry_index() -> dict[str, tuple[str, ...]]:
    """Folded ``industries`` tag -> bundle slugs that claim it."""
    index: dict[str, set[str]] = {}
    for slug, bundle in load_bundles().items():
        for series in bundle.get("series") or []:
            for tag in series.get("industries") or []:
                index.setdefault(_fold(str(tag)), set()).add(slug)
    return {k: tuple(sorted(v)) for k, v in index.items()}


def bundles_for(terms: list[str], sic: str | None = None) -> list[str]:
    """Bundle slugs matching a record's sector, most authoritative signal first.

    A SIC code from SEC leads, then the explicit vertical map, then the bundles'
    own ``industries`` tags, then the goods economy as a floor. Order is stable
    so the same record resolves the same way on every run.
    """
    hits: list[str] = []
    from_sic = bundle_for_sic(sic)
    if from_sic:
        hits.append(from_sic)
    index = _industry_index()
    for term in terms:
        folded = _fold(str(term or ""))
        if not folded:
            continue
        for slug in VERTICAL_BUNDLES.get(folded, ()):
            if slug not in hits:
                hits.append(slug)
        if folded in index:
            for slug in index[folded]:
                if slug not in hits:
                    hits.append(slug)
    return hits or [FALLBACK_BUNDLE]


def latest_observations(series_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Latest stored observation per FRED series id. Database only — never fetches.

    Empty when the bundles have not been synced, which is a legitimate state:
    macro *links* are useful on their own, and inventing an observation to fill
    the gap would be exactly the kind of silent error this framework exists to
    prevent.
    """
    from public_data.models import ExternalSeries

    out: dict[str, dict[str, Any]] = {}
    rows = ExternalSeries.objects.filter(
        provider="fred", external_id__in=series_ids
    ).prefetch_related("observations")
    for series in rows:
        latest = series.observations.order_by("-observation_date").first()
        if latest:
            out[series.external_id] = {
                "date": latest.observation_date.isoformat(),
                "value": float(latest.value),
                "units": series.units,
            }
    return out


class FredMacroContext(BaseProvider):
    """Attach the FRED series that govern a record's sector.

    Free and offline: the bundles are committed reference data and the
    observations, when present, come from the warehouse.
    """

    name = "fred"
    requires = frozenset({"name"})
    provides = frozenset({"macro_bundle", "macro_series", "macro_scope", "reference"})
    cost = Cost.FREE
    # SEC's SIC code classifies a filer better than a supplier list's end-market
    # tags do, so wait for it rather than answering from the seed.
    defer_to = frozenset({"edgar_submissions"})

    def run(self, rec, ctx):
        terms = []
        for key in ("industry", "sic_description", "vertical"):
            value = rec.get(key)
            if isinstance(value, list):
                terms.extend(value)
            elif value:
                terms.append(value)
        slugs = bundles_for(terms, sic=rec.get("sic"))[:MAX_BUNDLES_PER_RECORD]

        # FRED measures the United States. For a supplier anywhere else these
        # series are a proxy for its end markets, not a measurement of them, and
        # the record has to say which.
        iso2_code = rec.get("geo_iso2") or rec.get("country_iso")
        domestic = iso2_code == "US"
        scope = "domestic_us" if domestic else "us_proxy"
        confidence = 0.9 if domestic else 0.4
        caveat = (
            ""
            if domestic
            else " (US series used as a proxy: FRED does not measure this jurisdiction)"
        )

        bundles = load_bundles()
        chosen: list[dict[str, Any]] = []
        for slug in slugs:
            bundle = bundles.get(slug)
            if not bundle:
                continue
            yield Claim(
                "macro_bundle",
                slug,
                confidence,
                self.name,
                Evidence(
                    url=FRED_SERIES_URL.format(series_id=(bundle["series"][0]["id"])),
                    locator=f"bundle:{slug}",
                    snippet=f"{bundle.get('name')}: {bundle.get('description', '')}"[:300],
                ),
            )
            for series in (bundle.get("series") or [])[:3]:
                if len(chosen) >= MAX_SERIES_PER_RECORD:
                    break
                chosen.append({**series, "bundle": slug})

        if not chosen:
            return

        yield Claim(
            "macro_scope",
            scope,
            1.0,
            self.name,
            Evidence(locator=f"fred_scope:{iso2_code or 'unknown'}"),
            verified=True,
        )

        observations = latest_observations([s["id"] for s in chosen])
        for series in chosen:
            series_id = series["id"]
            url = FRED_SERIES_URL.format(series_id=series_id)
            latest = observations.get(series_id)
            payload = {
                "id": series_id,
                "bundle": series["bundle"],
                "note": series.get("note"),
                "frequency": series.get("frequency"),
                "url": url,
                "scope": scope,
                "latest_date": (latest or {}).get("date"),
                "latest_value": (latest or {}).get("value"),
            }
            ev = Evidence(
                url=url,
                locator=f"fred:{series_id}",
                snippet=(str(series.get("note") or series_id)[:260] + caveat)[:300],
            )
            yield Claim("macro_series", payload, confidence, self.name, ev)
            yield Claim(
                "reference",
                {"url": url, "title": f"FRED {series_id}", "kind": "fred.stlouisfed.org"},
                confidence,
                self.name,
                ev,
            )


class FredDeflator(BaseProvider):
    """Restate a reported revenue in constant dollars using a FRED price index.

    Requires ``revenue_reported`` and the fiscal period it belongs to, which only
    ``edgar_facts`` supplies — so this fires exactly on the rows where a filed
    number exists and is worth comparing across years.

    Emits nothing when the needed index is not in the database. A deflator
    guessed from a neighbouring year is not a deflator, it is a rounding error
    with provenance.
    """

    name = "fred_deflator"
    requires = frozenset({"revenue_reported", "revenue_period_end"})
    provides = frozenset(
        {"revenue_real", "revenue_real_base", "revenue_deflator", "revenue_deflator_series"}
    )
    cost = Cost.FREE

    def run(self, rec, ctx):
        from public_data.models import ExternalSeries

        try:
            nominal = float(rec.get("revenue_reported"))
        except (TypeError, ValueError):
            return
        period_end = str(rec.get("revenue_period_end") or "")[:10]
        if not period_end or nominal <= 0:
            return

        bundle_slugs = rec.get("macro_bundle") or []
        if isinstance(bundle_slugs, str):
            bundle_slugs = [bundle_slugs]
        series_id = next((DEFLATORS[s] for s in bundle_slugs if s in DEFLATORS), DEFAULT_DEFLATOR)

        series = ExternalSeries.objects.filter(provider="fred", external_id=series_id).first()
        if not series:
            return

        # The index value in the company's own fiscal period, and the latest —
        # the ratio between them is the restatement.
        at_period = (
            series.observations.filter(observation_date__lte=period_end)
            .order_by("-observation_date")
            .first()
        )
        latest = series.observations.order_by("-observation_date").first()
        if not at_period or not latest or not at_period.value:
            return

        factor = float(latest.value) / float(at_period.value)
        url = FRED_SERIES_URL.format(series_id=series_id)
        ev = Evidence(
            url=url,
            locator=f"fred:{series_id}:{at_period.observation_date}->{latest.observation_date}",
            snippet=(
                f"{series_id} {at_period.value} at {at_period.observation_date} -> "
                f"{latest.value} at {latest.observation_date}; factor {factor:.4f}"
            ),
        )
        yield Claim("revenue_real", round(nominal * factor, 2), 0.9, self.name, ev, verified=True)
        yield Claim(
            "revenue_real_base",
            latest.observation_date.isoformat(),
            1.0,
            self.name,
            ev,
            verified=True,
        )
        yield Claim("revenue_deflator", round(factor, 6), 0.9, self.name, ev, verified=True)
        yield Claim("revenue_deflator_series", series_id, 1.0, self.name, ev, verified=True)
