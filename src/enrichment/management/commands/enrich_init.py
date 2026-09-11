"""Load a CSV list into an enrichment dataset."""

from django.core.management.base import BaseCommand, CommandError

from enrichment.adapters.csvlist import MAPPINGS, ColumnMap, load
from warehouse.models import EnrichmentDataset


class Command(BaseCommand):
    help = "Create or refresh an enrichment dataset from a CSV list of organizations."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", required=True, help="Slug to create or refresh")
        parser.add_argument("--csv", required=True, help="Path to the input CSV")
        parser.add_argument("--name", default="", help="Human-readable dataset name")
        parser.add_argument(
            "--mapping",
            default="manufacturing_v1",
            help=f"Named column mapping ({'|'.join(MAPPINGS)}) or 'custom'",
        )
        parser.add_argument(
            "--key", default="company", help="Identity column, when --mapping custom"
        )
        parser.add_argument("--encoding", default="utf-8")

    def handle(self, *args, **options):
        if options["mapping"] == "custom":
            cmap = ColumnMap(key=options["key"])
        elif options["mapping"] in MAPPINGS:
            cmap = MAPPINGS[options["mapping"]]
        else:
            raise CommandError(
                f"Unknown mapping {options['mapping']!r}; "
                f"choose from {', '.join(MAPPINGS)} or 'custom'"
            )

        dataset, created = EnrichmentDataset.objects.update_or_create(
            slug=options["dataset"],
            defaults={
                "name": options["name"] or options["dataset"],
                "source_path": options["csv"][:512],
            },
        )
        stats = load(dataset, options["csv"], cmap, encoding=options["encoding"])
        verb = "Created" if created else "Refreshed"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} dataset {dataset.slug}: {stats['rows']:,} rows "
                f"({stats['duplicates']:,} duplicates, {stats['skipped_blank']:,} blank)"
            )
        )
