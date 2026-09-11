"""Coverage and audit views over an enrichment dataset.

Two questions, both of which a master-data pipeline has to answer on demand:
how much of the list is actually known (``dataset_report``), and where did one
particular value come from (``record_evidence``).
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Q

from warehouse.models import (
    EnrichmentClaim,
    EnrichmentDataset,
    EnrichmentGoldenField,
    EnrichmentProviderRun,
    EnrichmentRecord,
)


def dataset_report(dataset: EnrichmentDataset) -> dict[str, Any]:
    """Coverage, trust and per-provider outcomes for one dataset."""
    records = EnrichmentRecord.objects.filter(dataset=dataset)
    total = records.count()
    claims = EnrichmentClaim.objects.filter(record__dataset=dataset)
    golden = EnrichmentGoldenField.objects.filter(record__dataset=dataset)

    def distinct_records_with(**filters) -> int:
        return claims.filter(**filters).values("record_id").distinct().count()

    coverage = {
        field: golden.filter(field=field).count()
        for field in (
            "cik",
            "website",
            "legal_name",
            "sic",
            "employees",
            "revenue_reported",
            "revenue_estimated",
            "revenue_real",
            "geo_iso2",
            "macro_scope",
            "parent_name",
        )
    }

    by_provider: dict[str, dict[str, int]] = {}
    for row in (
        EnrichmentProviderRun.objects.filter(record__dataset=dataset)
        .values("provider", "status")
        .annotate(n=Count("id"))
        .order_by("provider", "status")
    ):
        by_provider.setdefault(row["provider"], {})[row["status"]] = row["n"]

    return {
        "dataset": dataset.slug,
        "records": total,
        "claims": claims.count(),
        "golden_fields": golden.count(),
        "linked_companies": records.filter(company__isnull=False).count(),
        "cik_verified": distinct_records_with(field="cik", verified=True),
        "websites_verified": distinct_records_with(field="website", verified=True),
        "website_candidates_only": distinct_records_with(field="website_candidate"),
        "references": claims.filter(field="reference").count(),
        "contested_fields": golden.filter(contested=True).count(),
        "provider_errors": EnrichmentProviderRun.objects.filter(
            record__dataset=dataset, status="error"
        ).count(),
        "coverage": coverage,
        "by_provider": by_provider,
        "validation_status": _validation_mix(dataset),
    }


def _validation_mix(dataset: EnrichmentDataset) -> dict[str, int]:
    """How many records reached each validation tier — the trust distribution."""
    golden = EnrichmentGoldenField.objects.filter(record__dataset=dataset)
    with_cik = set(golden.filter(field="cik").values_list("record_id", flat=True))
    checks = dict(golden.filter(field="jurisdiction_check").values_list("record_id", "value"))
    with_geo = set(golden.filter(field="geo_iso2").values_list("record_id", flat=True))

    out = {
        "sec_registrant": 0,
        "jurisdiction_consistent": 0,
        "jurisdiction_conflict": 0,
        "geo_only": 0,
        "unchecked": 0,
    }
    for record_id in EnrichmentRecord.objects.filter(dataset=dataset).values_list("pk", flat=True):
        if record_id in with_cik:
            out["sec_registrant"] += 1
        elif checks.get(record_id) == "inconsistent":
            out["jurisdiction_conflict"] += 1
        elif checks.get(record_id) == "consistent":
            out["jurisdiction_consistent"] += 1
        elif record_id in with_geo:
            out["geo_only"] += 1
        else:
            out["unchecked"] += 1
    return out


def record_evidence(dataset: EnrichmentDataset, name: str) -> dict[str, Any] | None:
    """Every claim and its source for one record — the audit view.

    This is the answer to "why does it say that?", and the reason providers are
    forbidden from writing to a record in the first place.
    """
    record = (
        EnrichmentRecord.objects.filter(Q(dataset=dataset) & Q(source_key__icontains=name))
        .order_by("pk")
        .first()
    )
    if record is None:
        return None

    claims = [
        {
            "field": c.field,
            "value": c.value,
            "confidence": c.confidence,
            "provider": c.provider,
            "verified": c.verified,
            "evidence_url": c.ev_url,
            "evidence_snippet": c.ev_snippet,
            "evidence_locator": c.ev_locator,
            "retrieved_at": c.retrieved_at.isoformat(),
        }
        for c in record.claims.all().order_by("field", "-verified", "-confidence")
    ]
    golden = [
        {
            "field": g.field,
            "value": g.value,
            "confidence": g.confidence,
            "provider": g.provider,
            "evidence_url": g.ev_url,
            "rivals": g.rivals,
            "contested": g.contested,
        }
        for g in record.golden_fields.all().order_by("field")
    ]
    return {
        "record_id": record.pk,
        "source_key": record.source_key,
        "company_id": record.company_id,
        "seed": record.seed,
        "claims": claims,
        "golden": golden,
        "provider_runs": [
            {"provider": r.provider, "status": r.status, "detail": r.detail}
            for r in record.provider_runs.all().order_by("provider")
        ],
    }
