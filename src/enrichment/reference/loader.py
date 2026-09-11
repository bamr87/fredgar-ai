"""Committed enrichment reference data, read through the shared reference loader.

Lives under ``data/reference/enrichment/`` with the rest of the runtime reference
JSON rather than as Python literals, so it is diffable, regenerable, and reaches
Docker images by the path everything else already uses.

``iso3166.json`` is regenerated with ``manage.py build_enrichment_reference``
(build-time dependencies only). ``business_registries.json`` is curated by hand —
which register is authoritative and which legal forms it can create are editorial
judgements with no upstream dataset to regenerate from.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sec_edgar.reference_data import load_reference_json

ISO3166_FILE = "enrichment/iso3166.json"
REGISTRIES_FILE = "enrichment/business_registries.json"


@lru_cache(maxsize=1)
def countries() -> dict[str, dict]:
    """ISO 3166-1 alpha-2 -> country record (iso3, UN region, centroid, currency…)."""
    return load_reference_json(ISO3166_FILE)["countries"]


@lru_cache(maxsize=1)
def subdivisions() -> dict[str, dict]:
    """ISO 3166-1 alpha-2 -> {ISO 3166-2 code: {"name": …}}."""
    return load_reference_json(ISO3166_FILE)["subdivisions"]


@lru_cache(maxsize=1)
def business_registries() -> dict[str, Any]:
    """Registries per jurisdiction, the GLEIF fallback, and legal-form mappings."""
    return load_reference_json(REGISTRIES_FILE)
