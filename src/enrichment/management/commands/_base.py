"""Shared argument handling for the ``enrich_*`` commands."""

from __future__ import annotations

from django.core.management.base import CommandError

from warehouse.models import EnrichmentDataset


def add_dataset_argument(parser) -> None:
    parser.add_argument(
        "--dataset", required=True, help="Dataset slug (see manage.py enrich_report)"
    )


def get_dataset(slug: str) -> EnrichmentDataset:
    try:
        return EnrichmentDataset.objects.get(slug=slug)
    except EnrichmentDataset.DoesNotExist as exc:
        known = ", ".join(EnrichmentDataset.objects.values_list("slug", flat=True)) or "none"
        raise CommandError(f"No dataset {slug!r}. Known datasets: {known}") from exc
