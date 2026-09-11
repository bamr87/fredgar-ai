"""Claims -> golden record, for a whole dataset."""

from __future__ import annotations

import logging

from warehouse.models import EnrichmentDataset, EnrichmentRecord

from ..core import store
from ..core.golden import write_golden

logger = logging.getLogger(__name__)


def resolve_dataset(dataset: EnrichmentDataset) -> dict:
    """Re-resolve every record with claims. Idempotent — golden is always rebuilt.

    Resolution is deliberately a separate step from the run. A provider that
    misbehaved can have its claims deleted and the record re-resolved without
    re-running anything else, which is the whole point of keeping claims and
    conclusions apart.
    """
    records = 0
    fields = 0
    qs = (
        EnrichmentRecord.objects.filter(dataset=dataset)
        .prefetch_related("claims", "provider_runs")
        .order_by("pk")
    )
    for row in qs.iterator(chunk_size=500):
        rec = store.load_record(row)
        if not rec.claims:
            continue
        fields += write_golden(row.pk, rec)
        records += 1
    logger.info("Resolved %s records into %s golden fields", records, fields)
    return {"records_resolved": records, "golden_fields": fields}


def refresh_providers(dataset: EnrichmentDataset, providers: list[str]) -> dict:
    """Discard specific providers' claims and checkpoints so they genuinely re-run.

    The counterpart to append-only claims: re-running a provider after fixing a
    bug is only meaningful if its previous output goes away first, and only safe
    if nothing else does. Every other provider's findings survive untouched — the
    record rebuilds from whatever claims remain.
    """
    from warehouse.models import EnrichmentClaim, EnrichmentProviderRun

    claims, _ = EnrichmentClaim.objects.filter(
        record__dataset=dataset, provider__in=providers
    ).delete()
    runs, _ = EnrichmentProviderRun.objects.filter(
        record__dataset=dataset, provider__in=providers
    ).delete()
    logger.info("Refreshed %s: dropped %s claims, %s runs", providers, claims, runs)
    return {"claims": claims, "runs": runs}
