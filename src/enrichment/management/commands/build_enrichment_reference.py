"""Regenerate the committed enrichment reference JSON from authoritative sources.

The framework reads ``data/reference/enrichment/*.json`` at runtime and has no
third-party dependency for it. The packages below are **build-time only**, so the
shipped tables cost nothing to import and cannot drift with a library upgrade —
which is why this is a command you run deliberately rather than a lookup that
happens on import.

    pip install pycountry country_converter countryinfo
    cd src && python manage.py build_enrichment_reference

Only ``iso3166.json`` is generated. ``business_registries.json`` is curated by
hand: which register is authoritative in a jurisdiction, and which legal forms it
can create, are editorial judgements with no upstream dataset to regenerate from.
"""

from __future__ import annotations

import datetime as dt
import json
import warnings
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from sec_edgar.reference_data import reference_root


class Command(BaseCommand):
    help = "Rebuild data/reference/enrichment/iso3166.json from pycountry and friends."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="",
            help="Output path (default: data/reference/enrichment/iso3166.json)",
        )
        parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")

    def handle(self, *args, **options):
        warnings.filterwarnings("ignore")
        try:
            import country_converter as coco
            import pycountry
            from countryinfo import CountryInfo
        except ImportError as exc:
            raise CommandError(
                "Build-time dependencies missing. "
                "pip install pycountry country_converter countryinfo"
            ) from exc

        converter = coco.CountryConverter().data
        by_iso2 = {
            row["ISO2"]: row for _, row in converter.iterrows() if isinstance(row.get("ISO2"), str)
        }

        countries: dict[str, dict] = {}
        for country in pycountry.countries:
            record = {
                "name": country.name,
                "official_name": getattr(country, "official_name", None),
                "iso3": country.alpha_3,
                "numeric": country.numeric,
            }
            row = by_iso2.get(country.alpha_2)
            if row is not None:
                record["continent"] = row.get("continent")
                record["un_region"] = row.get("UNregion")
                record["eu"] = bool(isinstance(row.get("EU"), str) and row.get("EU"))
                record["oecd"] = bool(row.get("OECD") == row.get("OECD") and row.get("OECD"))
            info: dict[str, Any] = {}
            try:
                # countryinfo declares a fully-populated TypedDict it does not
                # always return, so this is read as a plain mapping.
                info = dict(CountryInfo(country.alpha_2).info())
            except Exception:  # noqa: BLE001 - countryinfo raises freely on gaps
                info = {}
            if info:
                latlng = info.get("latlng") or []
                record["lat"], record["lon"] = (
                    (float(latlng[0]), float(latlng[1])) if len(latlng) == 2 else (None, None)
                )
                capital = info.get("capital_latlng") or []
                record["capital"] = info.get("capital")
                record["capital_lat"], record["capital_lon"] = (
                    (float(capital[0]), float(capital[1])) if len(capital) == 2 else (None, None)
                )
                record["region"] = record.get("continent") or info.get("region")
                record["subregion"] = record.get("un_region") or info.get("subregion")
                record["tld"] = list(info.get("tld") or [])[:3]
                record["currencies"] = list(info.get("currencies") or [])[:3]
                record["area_km2"] = info.get("area")
                record["population"] = info.get("population")
            countries[country.alpha_2] = {
                k: v for k, v in record.items() if v not in (None, [], "")
            }

        # ISO 3166-2, for resolving a state or province out of a registry address.
        subdivisions: dict[str, dict] = {}
        for sub in pycountry.subdivisions:
            subdivisions.setdefault(sub.country_code, {})[sub.code] = {
                "name": sub.name,
                "type": sub.type,
            }

        total_subs = sum(len(v) for v in subdivisions.values())
        self.stdout.write(f"countries: {len(countries):,}  subdivisions: {total_subs:,}")
        if options["dry_run"]:
            return

        payload = {
            "_generated": dt.date.today().isoformat(),
            "_sources": [
                "pycountry (ISO 3166-1 / 3166-2)",
                "country_converter (UN region, continent, EU/OECD membership)",
                "countryinfo (centroids, capitals, ccTLDs, currencies)",
            ],
            "countries": countries,
            "subdivisions": subdivisions,
        }
        out_path = (
            Path(options["out"])
            if options["out"]
            else (reference_root() / "enrichment" / "iso3166.json")
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8"
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {out_path}"))
