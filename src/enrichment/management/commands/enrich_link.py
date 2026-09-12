"""Link resolved records to warehouse companies by verified CIK."""

from django.core.management.base import BaseCommand

from enrichment.services import link_companies

from ._base import add_dataset_argument, get_dataset


class Command(BaseCommand):
    help = "Attach enrichment records to warehouse Company rows via their verified CIK."

    def add_arguments(self, parser):
        add_dataset_argument(parser)
        parser.add_argument(
            "--no-create",
            action="store_true",
            help="Only link to companies the warehouse already tracks",
        )

    def handle(self, *args, **options):
        stats = link_companies(
            get_dataset(options["dataset"]), create_missing=not options["no_create"]
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Linked {stats['linked']:,} records "
                f"({stats['created']:,} companies created, "
                f"{stats['skipped_unverified']:,} skipped as unverified)."
            )
        )
