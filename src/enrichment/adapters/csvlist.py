"""Generic CSV list ingestion.

The framework must not care that your list happens to have a column called
``company``. A mapping declares which of your columns feed which seed fields, so
a supplier extract, an AP vendor dump and a CRM export all enter the same way.

    MAPPING = ColumnMap(
        key="company",                       # the identity column (required)
        fields={"country": "countries", "n_sites": "n_sites"},
        multi={"alias": "name_variants", "vertical": "verticals"},
    )
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field

from warehouse.models import EnrichmentDataset

from ..core import store
from ..normalize import blocking_key, clean, iso2

SPLIT_CHARS = ",;|"


def _split(value: str) -> list[str]:
    if not value:
        return []
    out, cur = [], value.replace("…", "")
    for ch in SPLIT_CHARS[1:]:
        cur = cur.replace(ch, ",")
    for part in cur.split(","):
        p = part.strip()
        if p:
            out.append(p)
    return out


@dataclass
class ColumnMap:
    key: str  # column holding the entity name
    fields: dict = field(default_factory=dict)  # seed_field -> column
    multi: dict = field(default_factory=dict)  # seed_field -> column (list-valued)
    party_type: str = "vendor"  # vendor | customer | both | prospect


def load(
    dataset: EnrichmentDataset,
    csv_path: str,
    cmap: ColumnMap,
    encoding: str = "utf-8",
) -> dict:
    """Ingest a CSV into a dataset. Idempotent: re-running refreshes seeds in place."""
    stats = {"rows": 0, "skipped_blank": 0, "duplicates": 0}
    seen: set[str] = set()

    with open(csv_path, newline="", encoding=encoding, errors="replace") as fh:
        for row in csv.DictReader(fh):
            name = (row.get(cmap.key) or "").strip()
            if not name:
                stats["skipped_blank"] += 1
                continue
            if name in seen:
                stats["duplicates"] += 1
                continue
            seen.add(name)

            seed = {
                "name": name,
                "clean_name": clean(name),
                "blocking_key": blocking_key(name),
                "party_type": cmap.party_type,
            }

            for target, col in cmap.fields.items():
                value = (row.get(col) or "").strip()
                if value:
                    seed[target] = value

            for target, col in cmap.multi.items():
                values = _split(row.get(col) or "")
                if values:
                    seed[target] = values

            # Keep the WHOLE country list. Collapsing it to the first entry
            # discards the only evidence that can later place the headquarters:
            # "Akzo Nobel Nederland BV" led with United Kingdom and resolved to
            # GB, and nothing downstream could recover the Netherlands because
            # the list had already been thrown away at ingest.
            c = seed.get("country")
            if isinstance(c, list):
                all_countries = c
            elif isinstance(c, str):
                all_countries = _split(c)
            else:
                all_countries = []
            if all_countries:
                seed["countries"] = all_countries  # full operating footprint
                seed["country"] = all_countries[0]  # first listed — a GUESS at HQ
                if iso2(all_countries[0]):
                    seed["country_iso"] = iso2(all_countries[0])
                seen_iso, iso_list = set(), []
                for x in all_countries:
                    code = iso2(x)
                    if code and code not in seen_iso:
                        seen_iso.add(code)
                        iso_list.append(code)
                if iso_list:
                    seed["countries_iso"] = iso_list

            store.upsert_record(dataset, name, seed)
            stats["rows"] += 1
    return stats


# The mapping for the manufacturing supplier list this framework was built against.
MANUFACTURING_V1 = ColumnMap(
    key="company",
    fields={
        "country": "countries",
        "n_sites": "n_sites",
        "n_countries": "n_countries",
        "region": "regions",
    },
    multi={"alias": "name_variants", "parent_code": "parent_codes", "vertical": "verticals"},
    party_type="vendor",
)

# The same list after its first pass, as exported by ``master_list_v2.csv``.
MASTER_LIST_V2 = ColumnMap(
    key="input_name",
    fields={
        "country": "hq_country",
        "n_sites": "n_sites",
        "n_countries": "n_countries",
        "employees": "employees",
        "ticker": "ticker",
        "cik": "cik",
    },
    multi={"vertical": "all_verticals"},
    party_type="vendor",
)

MAPPINGS = {"manufacturing_v1": MANUFACTURING_V1, "master_list_v2": MASTER_LIST_V2}
