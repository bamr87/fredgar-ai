"""Django-ORM persistence for records, claims and evidence.

The original framework kept this in a standalone SQLite file. Moving it onto the
warehouse models is what makes enrichment a first-class part of fredgar: the
same Postgres (or SQLite) database that holds filings and facts holds the claims,
so a resolved CIK can join straight through to a company's financials.

Claims stay append-only. A later run of the same provider replaces only its own
row for that (record, field, value), so re-running one source after fixing a bug
loses nothing the others found.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone

from warehouse.models import (
    EnrichmentClaim,
    EnrichmentDataset,
    EnrichmentProviderRun,
    EnrichmentRecord,
)

from .model import Claim, Evidence, Record


def value_hash(value: Any) -> str:
    """Stable digest of a JSON value — the uniqueness key for a claim."""
    return hashlib.sha1(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def get_dataset(slug: str) -> EnrichmentDataset:
    return EnrichmentDataset.objects.get(slug=slug)


def upsert_record(dataset: EnrichmentDataset, source_key: str, seed: dict) -> int:
    """Insert or refresh one input row. The seed is authoritative; fields mirror it."""
    obj, _ = EnrichmentRecord.objects.update_or_create(
        dataset=dataset,
        source_key=source_key,
        defaults={"seed": seed, "fields": dict(seed)},
    )
    return obj.pk


def load_record(row: EnrichmentRecord) -> Record:
    """Rebuild the in-memory record from its immutable seed plus its CURRENT claims.

    Nothing is inherited from the ``fields`` cache. Delete a provider's claims and
    its contribution disappears, which is what makes re-running a fixed provider
    actually re-run it.
    """
    seed = dict(row.seed or {})
    if not seed:  # rows written before seed existed
        seed = dict(row.fields or {})
    rec = Record(row.pk, row.source_key, dict(seed))

    promoted: dict[str, Any] = {}
    # Ordered so verified / high-confidence claims land last and win.
    for c in row.claims.all().order_by("verified", "confidence"):
        claim = Claim(
            field=c.field,
            value=c.value,
            confidence=c.confidence,
            provider=c.provider,
            evidence=Evidence(
                url=c.ev_url or None,
                snippet=c.ev_snippet or None,
                locator=c.ev_locator or None,
                retrieved_at=c.retrieved_at.isoformat(),
            ),
            verified=c.verified,
        )
        rec.add(claim)
        if claim.field not in seed:
            promoted[claim.field] = claim.value
    rec.fields.update(promoted)
    rec.ran = set(row.provider_runs.values_list("provider", flat=True))
    return rec


def load_records(dataset: EnrichmentDataset, limit: int | None = None) -> list[Record]:
    """Load a dataset's records with claims and run-state prefetched (2 extra queries)."""
    qs = (
        EnrichmentRecord.objects.filter(dataset=dataset)
        .prefetch_related("claims", "provider_runs")
        .order_by("pk")
    )
    if limit:
        qs = qs[:limit]
    return [load_record(row) for row in qs]


@transaction.atomic
def save_claims(record_id: int, claims: Iterable[Claim]) -> int:
    """Upsert claims for one record. Returns how many rows were written."""
    rows = []
    for c in claims:
        retrieved = c.evidence.retrieved_at
        rows.append(
            EnrichmentClaim(
                record_id=record_id,
                field=c.field[:64],
                value=c.value,
                value_hash=value_hash(c.value),
                confidence=float(c.confidence),
                provider=c.provider[:64],
                verified=bool(c.verified),
                ev_url=(c.evidence.url or "")[:1024],
                ev_snippet=(c.evidence.snippet or "")[:600],
                ev_locator=(c.evidence.locator or "")[:255],
                retrieved_at=_as_datetime(retrieved),
            )
        )
    if not rows:
        return 0
    EnrichmentClaim.objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=["record", "field", "value_hash", "provider"],
        update_fields=[
            "value",
            "confidence",
            "verified",
            "ev_url",
            "ev_snippet",
            "ev_locator",
            "retrieved_at",
        ],
    )
    return len(rows)


def mark_run(record_id: int, provider: str, status: str, detail: str | None, ts) -> None:
    EnrichmentProviderRun.objects.update_or_create(
        record_id=record_id,
        provider=provider[:64],
        defaults={
            "status": status[:16],
            "detail": (detail or "")[:300],
            "ran_at": _as_datetime(ts),
        },
    )


def set_fields(record_id: int, fields: dict) -> None:
    EnrichmentRecord.objects.filter(pk=record_id).update(fields=fields)


def _as_datetime(value):
    """Accept an ISO string (what Evidence carries) or a datetime; never naive."""
    if value is None:
        return timezone.now()
    if isinstance(value, str):
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(value)
        if parsed is None:
            return timezone.now()
        value = parsed
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.utc)
    return value
