"""Export the golden record as a customer/vendor master CSV."""

from django.core.management.base import BaseCommand

from enrichment.export.master import export_csv

from ._base import add_dataset_argument, get_dataset


class Command(BaseCommand):
    help = "Write the MDM export for a dataset."

    def add_arguments(self, parser):
        add_dataset_argument(parser)
        parser.add_argument("--out", required=True, help="Output CSV path")

    def handle(self, *args, **options):
        stats = export_csv(get_dataset(options["dataset"]), options["out"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {stats['rows']:,} rows to {stats['out']} "
                f"({stats['revenue_reported']:,} with reported revenue, "
                f"{stats['below_30pct_complete']:,} below 30% complete)."
            )
        )
