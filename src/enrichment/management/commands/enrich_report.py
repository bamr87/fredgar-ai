"""Coverage and trust report for an enrichment dataset."""

import json

from django.core.management.base import BaseCommand

from enrichment.services import dataset_report
from warehouse.models import EnrichmentDataset

from ._base import get_dataset


class Command(BaseCommand):
    help = "Print coverage, trust and per-provider outcomes for a dataset."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", help="Dataset slug (omit to list all datasets)")
        parser.add_argument("--json", action="store_true", help="Machine-readable output")

    def handle(self, *args, **options):
        if not options["dataset"]:
            for d in EnrichmentDataset.objects.all():
                self.stdout.write(f"{d.slug:24s} {d.records.count():>8,} records  {d.name}")
            return

        stats = dataset_report(get_dataset(options["dataset"]))
        if options["json"]:
            self.stdout.write(json.dumps(stats, indent=2, default=str))
            return

        total = max(stats["records"], 1)
        self.stdout.write(f"dataset            : {stats['dataset']}")
        self.stdout.write(f"records            : {stats['records']:,}")
        self.stdout.write(f"claims             : {stats['claims']:,}")
        self.stdout.write(f"golden fields      : {stats['golden_fields']:,}")
        self.stdout.write(
            f"CIK verified       : {stats['cik_verified']:,}  ({stats['cik_verified'] / total:.1%})"
        )
        self.stdout.write(f"linked companies   : {stats['linked_companies']:,}")
        self.stdout.write(
            f"websites verified  : {stats['websites_verified']:,}  "
            f"({stats['websites_verified'] / total:.1%})"
        )
        self.stdout.write(f"candidates only    : {stats['website_candidates_only']:,}")
        self.stdout.write(f"references found   : {stats['references']:,}")
        self.stdout.write(f"contested fields   : {stats['contested_fields']:,}")
        self.stdout.write(f"provider errors    : {stats['provider_errors']:,}")

        self.stdout.write("\ncoverage (records with a resolved value):")
        for field, n in stats["coverage"].items():
            self.stdout.write(f"   {field:22s} {n:>8,}  {n / total:>6.1%}")

        self.stdout.write("\nvalidation tier:")
        for tier, n in stats["validation_status"].items():
            self.stdout.write(f"   {tier:22s} {n:>8,}  {n / total:>6.1%}")

        self.stdout.write("\nby provider:")
        for provider, outcomes in sorted(stats["by_provider"].items()):
            summary = "  ".join(f"{k}={v:,}" for k, v in sorted(outcomes.items()))
            self.stdout.write(f"   {provider:22s} {summary}")
