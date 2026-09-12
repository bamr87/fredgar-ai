"""Join resolved enrichment records to warehouse companies.

This is the step that makes enrichment part of fredgar rather than a parallel
universe. Once a record has a golden ``cik``, it names an entity the warehouse
already models — so the record gets a ``Company`` foreign key, and the company
gets ``ExternalIdentifier`` rows for every identifier the enrichment found. From
there a vendor row joins straight through to that company's filings, XBRL facts,
derived metrics and leadership analysis.

Only *verified* CIK claims are linked. ``edgar_issuer`` marks a CIK verified only
on an exact normalised-name match with no close rival, and that threshold exists
precisely here: a wrong link does not raise, it silently attaches one company's
audited financials to another company's vendor record.
"""

from __future__ import annotations

import logging

from django.db import transaction

from warehouse.models import (
    Company,
    EnrichmentDataset,
    EnrichmentGoldenField,
    EnrichmentRecord,
)
from warehouse.services.identity import index_company_identifiers

logger = logging.getLogger(__name__)


def link_companies(dataset: EnrichmentDataset, *, create_missing: bool = True) -> dict:
    """Attach records to warehouse companies by verified CIK.

    ``create_missing`` controls whether a CIK with no ``Company`` row creates one.
    Off, the linker only connects to issuers the warehouse already tracks — which
    is what you want when the warehouse is a curated cohort rather than a mirror
    of all of EDGAR.
    """
    stats = {"linked": 0, "created": 0, "skipped_unverified": 0, "identifiers": 0}

    # A verified CIK claim is the gate; the golden row carries the resolved value.
    verified_record_ids = set(
        EnrichmentRecord.objects.filter(
            dataset=dataset, claims__field="cik", claims__verified=True
        ).values_list("pk", flat=True)
    )

    golden = EnrichmentGoldenField.objects.filter(
        record__dataset=dataset, field="cik"
    ).select_related("record")

    for row in golden.iterator(chunk_size=500):
        cik = str(row.value or "").strip()
        if not cik:
            continue
        if row.record_id not in verified_record_ids:
            stats["skipped_unverified"] += 1
            continue

        company = Company.objects.filter(cik=cik).first()
        if company is None:
            if not create_missing:
                continue
            company = Company.objects.create(
                cik=cik,
                name=_golden_value(row.record_id, "legal_name") or row.record.source_key,
                ticker=_golden_value(row.record_id, "ticker") or None,
                sic_code=_golden_value(row.record_id, "sic") or None,
                sic_description=_golden_value(row.record_id, "sic_description") or None,
                hq_city=_golden_value(row.record_id, "hq_city") or None,
            )
            stats["created"] += 1

        with transaction.atomic():
            EnrichmentRecord.objects.filter(pk=row.record_id).update(company=company)
            stats["identifiers"] += index_company_identifiers(company)
        stats["linked"] += 1

    logger.info(
        "Linked %s enrichment records to companies (%s created)", stats["linked"], stats["created"]
    )
    return stats


def _golden_value(record_id: int, field: str):
    row = EnrichmentGoldenField.objects.filter(record_id=record_id, field=field).first()
    if not row:
        return None
    value = row.value
    return str(value) if value not in (None, "") else None
