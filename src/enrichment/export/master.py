"""Export the golden record as a customer/vendor master.

Master data is judged on trustworthiness, not row count. So every exported party
carries a completeness score, a count of contested fields, and the evidence URL
behind its most important attributes. A record you cannot audit is not master
data; it is a spreadsheet with ambitions.
"""

from __future__ import annotations

import csv
from typing import Any, Iterator

from warehouse.models import EnrichmentDataset, EnrichmentGoldenField, EnrichmentRecord

from ..providers.webdiscovery import registrable_domain

# Weights encode what a vendor/customer master is actually FOR: paying the right
# entity, classifying spend, and rolling up to a parent.
#
# These are keyed on EXPORT COLUMN names, not on provider field names. Keying
# them on internal field names silently scored ~0 for every record, because the
# names drifted apart ("revenue" vs "revenue_estimated") with nothing to catch
# it — a completeness metric that is itself incomplete is worse than none.
COMPLETENESS_WEIGHTS = {
    "legal_name": 2.0,
    "website": 3.0,
    "lei": 2.5,
    "country": 1.0,
    "hq_city": 1.0,
    "naics": 1.5,
    "vertical": 1.0,
    "industry": 1.0,
    "employees": 1.5,
    "revenue_reported": 2.0,
    "revenue_estimated": 0.5,
    "parent_name": 1.0,
    "phone": 0.5,
    "reference_count": 1.0,
    "ticker": 0.5,
    "vat": 1.0,
    # Geography and registry validation are what make a party record payable.
    "geo_iso2": 1.0,
    "geo_subregion": 0.5,
    "geo_lat": 0.5,
    "registration_number": 2.0,
    "registry_name": 0.5,
    # SEC identity: the join key into filings, facts and every derived metric.
    "cik": 2.0,
    "sic": 1.0,
    "ein": 1.0,
    "state_of_incorporation": 0.5,
}
MAX_SCORE = sum(COMPLETENESS_WEIGHTS.values())

# A resolved value that came only from a model is not the same as a known fact.
# Estimated revenue is already weighted low; this keeps it from ever masquerading
# as coverage that a buyer or an AP clerk could act on.
ESTIMATED_FIELDS = {"revenue_estimated", "geo_lat"}  # a centroid is not a location

EXPORT_COLUMNS = [
    "party_id",
    "party_type",
    "input_name",
    "legal_name",
    "website",
    "domain",
    # --- identifiers ---
    "lei",
    "cik",
    "ticker",
    "exchanges",
    "ein",
    "vat",
    "state_of_incorporation",
    "entity_type",
    "fiscal_year_end",
    "aliases",
    # --- geography: ISO-normalized, with an explicit precision label ---
    "country",
    "geo_iso2",
    "geo_iso3",
    "geo_country",
    "geo_region",
    "geo_subregion",
    "geo_subdivision",
    "hq_country_inferred",
    "hq_inference_basis",
    "hq_city",
    "hq_postal",
    "hq_street",
    "geo_lat",
    "geo_lon",
    "geo_precision",
    "geo_currency",
    "geo_in_eu",
    "geo_in_oecd",
    "phone",
    # --- validation against public registers ---
    "registry_name",
    "registry_url",
    "registry_ra",
    "registry_free_api",
    "registration_number",
    "registration_authority",
    "entity_status",
    "legal_form_token",
    "form_jurisdictions",
    "jurisdiction_check",
    "registry_validated",
    "validation_status",
    "validation_reasons",
    # --- classification ---
    "vertical",
    "industry",
    "sic",
    "sic_description",
    "naics",
    # --- financials: reported and estimated, never blended ---
    "employees",
    "revenue_reported",
    "revenue_period_end",
    "revenue_currency",
    "revenue_estimated",
    "revenue_method",
    "revenue_basis",
    "revenue_real",
    "revenue_real_base",
    "revenue_deflator_series",
    "net_income",
    "total_assets",
    "stockholders_equity",
    # --- macro context (FRED) ---
    "macro_scope",
    "macro_bundles",
    "macro_series",
    # --- structure ---
    "parent_name",
    "parent_lei",
    "n_sites",
    "n_countries",
    "references",
    "reference_count",
    # --- trust ---
    "completeness",
    "hard_completeness",
    "contested_fields",
    "unverified_website",
    "last_seen",
]


def _as_list(value: Any) -> list:
    """Golden values are single or multi-valued by field; normalise for joining.

    A string is one value, not a sequence of characters. Treating it as the
    latter is how ``validation_reasons`` came out as ``f|o|r|m|_|c|o|u|n|t|r|y``.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _join(value: Any, sep: str = "|") -> str:
    return sep.join(str(v) for v in _as_list(value) if v not in (None, ""))


def build_rows(dataset: EnrichmentDataset) -> Iterator[dict]:
    """One assembled master row per record, with trust columns derived last."""
    golden_by_record: dict[int, dict[str, dict]] = {}
    for golden_row in EnrichmentGoldenField.objects.filter(record__dataset=dataset).iterator(
        chunk_size=2000
    ):
        golden_by_record.setdefault(golden_row.record_id, {})[golden_row.field] = {
            "value": golden_row.value,
            "confidence": golden_row.confidence,
            "provider": golden_row.provider,
            "ev_url": golden_row.ev_url,
            "contested": golden_row.contested,
        }

    verified_website_records = set(
        EnrichmentRecord.objects.filter(
            dataset=dataset, claims__field="website", claims__verified=True
        ).values_list("pk", flat=True)
    )

    for record in (
        EnrichmentRecord.objects.filter(dataset=dataset).order_by("pk").iterator(chunk_size=2000)
    ):
        seed = record.seed or record.fields or {}
        golden = golden_by_record.get(record.pk, {})

        def g(field: str, default=None):
            row = golden.get(field)
            return row["value"] if row else default

        contested = sorted(f for f, d in golden.items() if d["contested"])
        website = g("website")
        refs = _as_list(g("reference", []))
        ref_urls = [x.get("url") if isinstance(x, dict) else x for x in refs]
        macro_series = _as_list(g("macro_series", []))

        row = {
            "party_id": record.pk,
            "party_type": seed.get("party_type", "vendor"),
            "input_name": record.source_key,
            "legal_name": g("legal_name") or seed.get("name"),
            "website": website,
            "domain": registrable_domain(website) if website else None,
            "lei": g("lei"),
            "cik": g("cik"),
            "ticker": g("ticker"),
            "exchanges": "|".join(
                f"{e.get('exchange')}:{e.get('ticker')}"
                for e in _as_list(g("exchange", []))
                if isinstance(e, dict)
            ),
            "ein": g("ein"),
            "vat": g("vat"),
            "state_of_incorporation": g("state_of_incorporation"),
            "entity_type": g("entity_type"),
            "fiscal_year_end": g("fiscal_year_end"),
            "aliases": _join(g("alias", [])),
            "country": seed.get("country"),
            "geo_iso2": g("geo_iso2") or seed.get("country_iso"),
            "geo_iso3": g("geo_iso3"),
            "geo_country": g("geo_country"),
            "geo_region": g("geo_region"),
            "geo_subregion": g("geo_subregion"),
            "geo_subdivision": g("geo_subdivision"),
            "hq_country_inferred": g("hq_country_inferred"),
            "hq_inference_basis": g("hq_inference_basis"),
            "hq_city": g("hq_city"),
            "hq_postal": g("hq_postal"),
            "hq_street": g("hq_street"),
            "geo_lat": g("geo_lat"),
            "geo_lon": g("geo_lon"),
            "geo_precision": g("geo_precision"),
            "geo_currency": g("geo_currency"),
            "geo_in_eu": g("geo_in_eu"),
            "geo_in_oecd": g("geo_in_oecd"),
            "phone": _join(g("phone")),
            "registry_name": g("registry_name"),
            "registry_url": g("registry_url"),
            "registry_ra": g("registry_ra"),
            "registry_free_api": g("registry_free_api"),
            "registration_number": g("registration_number"),
            "registration_authority": g("registration_authority"),
            "entity_status": g("entity_status"),
            "legal_form_token": g("legal_form_token"),
            "form_jurisdictions": _join(g("form_jurisdictions", [])),
            "jurisdiction_check": g("jurisdiction_check"),
            "registry_validated": g("registry_validated"),
            "validation_reasons": _join(g("validation_reason", [])),
            "vertical": _join(seed.get("vertical", [])),
            "industry": _join(g("industry", [])),
            "sic": g("sic"),
            "sic_description": g("sic_description"),
            "naics": g("naics"),
            "employees": g("employees") or g("employees_site"),
            "revenue_reported": g("revenue_reported"),
            "revenue_period_end": g("revenue_period_end"),
            "revenue_currency": g("revenue_currency"),
            "revenue_estimated": g("revenue_estimated"),
            "revenue_method": g("revenue_method"),
            "revenue_real": g("revenue_real"),
            "revenue_real_base": g("revenue_real_base"),
            "revenue_deflator_series": g("revenue_deflator_series"),
            "net_income": g("net_income"),
            "total_assets": g("total_assets"),
            "stockholders_equity": g("stockholders_equity"),
            "macro_scope": g("macro_scope"),
            "macro_bundles": _join(g("macro_bundle", [])),
            "macro_series": "|".join(str(s.get("id")) for s in macro_series if isinstance(s, dict)),
            "parent_name": g("parent_name"),
            "parent_lei": g("parent_lei"),
            "n_sites": seed.get("n_sites"),
            "n_countries": seed.get("n_countries"),
            "references": "|".join(u for u in ref_urls if u),
            "reference_count": len(ref_urls),
            "contested_fields": ",".join(contested),
            # Loud on purpose: a website nobody verified is the most dangerous
            # cell in the whole export, because it looks exactly like a good one.
            "unverified_website": int(bool(website) and record.pk not in verified_website_records),
            "last_seen": record.updated_at.isoformat() if record.updated_at else None,
        }

        # Reported beats estimated, always, and the two are never averaged.
        row["revenue_basis"] = (
            "reported"
            if row["revenue_reported"] is not None
            else ("estimated" if row["revenue_estimated"] is not None else None)
        )

        # A single verdict, derived rather than asserted. Order matters: a
        # registry conflict outranks a clean jurisdiction check, and "unchecked"
        # is never allowed to look like "validated".
        rv, jc = row["registry_validated"], row["jurisdiction_check"]
        if rv == "conflict":
            row["validation_status"] = "conflict"
        elif rv == "validated":
            row["validation_status"] = "registry_validated"
        elif row["cik"]:
            # SEC holds an entity record for this filer, which is a register
            # confirming the name — weaker than a national register entry with a
            # registration number, stronger than an offline form check.
            row["validation_status"] = "sec_registrant"
        elif jc == "inconsistent":
            row["validation_status"] = "jurisdiction_conflict"
        elif jc == "consistent":
            row["validation_status"] = "jurisdiction_consistent"
        elif row["geo_iso2"]:
            row["validation_status"] = "geo_only"
        else:
            row["validation_status"] = "unchecked"

        # Completeness is scored on the ASSEMBLED row — having three conflicting
        # guesses is not the same as knowing something.
        empty: tuple[Any, ...] = (None, "", [], {}, 0, "0")
        got = sum(w for f, w in COMPLETENESS_WEIGHTS.items() if row.get(f) not in empty)
        row["completeness"] = round(got / MAX_SCORE, 3)
        # Coverage a human could act on: excludes modelled values.
        hard = sum(
            w
            for f, w in COMPLETENESS_WEIGHTS.items()
            if f not in ESTIMATED_FIELDS and row.get(f) not in empty
        )
        row["hard_completeness"] = round(hard / MAX_SCORE, 3)
        yield row


def export_csv(dataset: EnrichmentDataset, out_path: str) -> dict:
    rows = 0
    incomplete = 0
    reported = 0
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in build_rows(dataset):
            writer.writerow(row)
            rows += 1
            if row["completeness"] < 0.3:
                incomplete += 1
            if row["revenue_basis"] == "reported":
                reported += 1
    return {
        "rows": rows,
        "below_30pct_complete": incomplete,
        "revenue_reported": reported,
        "out": out_path,
    }
