"""Geographic normalization and validation.

Runs entirely offline against the embedded ISO 3166 reference, so it covers
100% of records regardless of network. What it cannot do offline is resolve a
street address to a point - that needs a geocoder, which is a separate provider
gated behind a fetch budget.
"""

from __future__ import annotations

import functools

from ..core.model import Claim, Evidence
from ..core.provider import BaseProvider, Cost
from ..normalize import _fold, iso2
from ..reference.loader import countries, subdivisions

# Names in operational lists that ISO does not use.
ALIASES = {
    "south korea": "KR",
    "north korea": "KP",
    "russia": "RU",
    "vietnam": "VN",
    "taiwan": "TW",
    "bolivia": "BO",
    "venezuela": "VE",
    "tanzania": "TZ",
    "iran": "IR",
    "syria": "SY",
    "laos": "LA",
    "moldova": "MD",
    "brunei": "BN",
    "macau": "MO",
    "macao": "MO",
    "hong kong": "HK",
    "czech republic": "CZ",
    "czechia": "CZ",
    "slovakia": "SK",
    "turkey": "TR",
    "turkiye": "TR",
    "uae": "AE",
    "united arab emirates": "AE",
    "usa": "US",
    "uk": "GB",
    "great britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "ivory coast": "CI",
    "cape verde": "CV",
    "swaziland": "SZ",
    "burma": "MM",
    "myanmar": "MM",
    "palestine": "PS",
    "kosovo": "XK",
}


@functools.lru_cache(maxsize=1)
def _name_index() -> dict[str, str]:
    """Every ISO name and official name, folded, for exact lookup. Built once."""
    out = {}
    for code, rec in countries().items():
        for n in (rec.get("name"), rec.get("official_name")):
            if n:
                out[_fold(n)] = code
    return out


def resolve_country(value: str | None) -> str | None:
    """Country string -> ISO 3166-1 alpha-2. Returns None rather than guessing."""
    if not value:
        return None
    v = _fold(value)
    if len(v) == 2 and v.upper() in countries():
        return v.upper()
    return _name_index().get(v) or ALIASES.get(v) or iso2(value)


class GeoNormalize(BaseProvider):
    """Attach the full geographic frame to every record. Free, total coverage."""

    name = "geo"
    requires = frozenset({"name"})
    provides = frozenset(
        {
            "geo_iso2",
            "geo_iso3",
            "geo_country",
            "geo_region",
            "geo_subregion",
            "geo_lat",
            "geo_lon",
            "geo_currency",
            "geo_cctld",
            "geo_in_eu",
            "geo_in_oecd",
            "geo_precision",
        }
    )
    cost = Cost.FREE

    def run(self, rec, ctx):
        raw = rec.get("country") or rec.get("hq_country_site")
        code = resolve_country(raw)
        if not code:
            if raw:
                yield Claim(
                    "validation_reason",
                    f"country_unresolved:{str(raw)[:40]}",
                    0.9,
                    self.name,
                    Evidence(locator="iso3166_lookup"),
                )
            return
        c = countries().get(code, {})
        ev = Evidence(locator=f"iso3166:{code}", snippet=c.get("name"))

        yield Claim("geo_iso2", code, 1.0, self.name, ev, verified=True)
        for fld, key in (
            ("geo_iso3", "iso3"),
            ("geo_country", "name"),
            ("geo_region", "region"),
            ("geo_subregion", "subregion"),
        ):
            if c.get(key):
                yield Claim(fld, c[key], 1.0, self.name, ev, verified=True)
        if c.get("currencies"):
            yield Claim("geo_currency", c["currencies"][0], 0.9, self.name, ev)
        if c.get("tld"):
            yield Claim("geo_cctld", c["tld"][0], 1.0, self.name, ev)
        yield Claim("geo_in_eu", bool(c.get("eu")), 1.0, self.name, ev)
        yield Claim("geo_in_oecd", bool(c.get("oecd")), 1.0, self.name, ev)

        # Coordinates. A country centroid is an honest coarse answer; label the
        # precision so nobody plots it as if it were a street address.
        city = rec.get("hq_city")
        if c.get("lat") is not None:
            yield Claim("geo_lat", c["lat"], 0.5, self.name, ev)
            yield Claim("geo_lon", c["lon"], 0.5, self.name, ev)
            yield Claim(
                "geo_precision",
                "city_known_not_geocoded" if city else "country_centroid",
                1.0,
                self.name,
                ev,
            )


class SubdivisionResolve(BaseProvider):
    """Map a registry-supplied region string to an ISO 3166-2 subdivision code."""

    name = "geo_subdivision"
    requires = frozenset({"geo_iso2", "hq_region_raw"})
    provides = frozenset({"geo_subdivision", "geo_subdivision_name"})
    cost = Cost.FREE

    def run(self, rec, ctx):
        code = rec.get("geo_iso2")
        raw = _fold(str(rec.get("hq_region_raw") or ""))
        if not code or not raw:
            return
        for sub_code, meta in (subdivisions().get(code) or {}).items():
            if _fold(meta["name"]) == raw or sub_code.lower() == raw:
                ev = Evidence(locator=f"iso3166-2:{sub_code}", snippet=meta["name"])
                yield Claim("geo_subdivision", sub_code, 0.95, self.name, ev)
                yield Claim("geo_subdivision_name", meta["name"], 0.95, self.name, ev)
                return


class Geocode(BaseProvider):
    """Street/city-level coordinates via a Nominatim-compatible endpoint.

    Not enabled by default: OSM's public instance asks for max 1 req/s and a
    real contact address. Point ctx.shared['nominatim'] at your own instance
    for anything above a few thousand rows.
    """

    name = "geocode"
    requires = frozenset({"hq_city", "geo_iso2"})
    provides = frozenset({"geo_lat", "geo_lon", "geo_precision"})
    cost = Cost.FETCH
    rate_per_sec = 1.0

    def run(self, rec, ctx):
        import json
        import urllib.parse

        base = (ctx.shared or {}).get("nominatim")
        if not base or ctx.http is None:
            return
        q = urllib.parse.urlencode(
            {
                "city": rec.get("hq_city"),
                "countrycodes": rec.get("geo_iso2").lower(),
                "format": "jsonv2",
                "limit": 1,
            }
        )
        try:
            data = json.loads(ctx.http.get(f"{base.rstrip('/')}/search?{q}"))
        except Exception:
            return
        if not data:
            return
        hit = data[0]
        ev = Evidence(
            url=f"{base}/search?{q}", locator="nominatim", snippet=hit.get("display_name", "")[:200]
        )
        yield Claim("geo_lat", float(hit["lat"]), 0.9, self.name, ev, verified=True)
        yield Claim("geo_lon", float(hit["lon"]), 0.9, self.name, ev, verified=True)
        yield Claim("geo_precision", "geocoded_city", 1.0, self.name, ev, verified=True)
