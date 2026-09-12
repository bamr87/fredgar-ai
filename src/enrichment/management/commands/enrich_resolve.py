"""Resolve claims into the golden record."""

from django.core.management.base import BaseCommand

from enrichment.services import resolve_dataset

from ._base import add_dataset_argument, get_dataset


class Command(BaseCommand):
    help = "Rebuild the golden record for a dataset from its current claims."

    def add_arguments(self, parser):
        add_dataset_argument(parser)

    def handle(self, *args, **options):
        stats = resolve_dataset(get_dataset(options["dataset"]))
        self.stdout.write(
            self.style.SUCCESS(
                f"Resolved {stats['records_resolved']:,} records into "
                f"{stats['golden_fields']:,} golden fields."
            )
        )
