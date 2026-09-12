"""Show what the provider graph WOULD do, before spending anything."""

from django.core.management.base import BaseCommand

from enrichment.pipeline import default_registry
from warehouse.models import EnrichmentRecord

from ._base import add_dataset_argument, get_dataset


class Command(BaseCommand):
    help = "Print the provider wave order for a dataset without running anything."

    def add_arguments(self, parser):
        add_dataset_argument(parser)
        parser.add_argument("--search", action="store_true", help="Include web search")
        parser.add_argument("--no-web", action="store_true", help="Exclude site fetching")

    def handle(self, *args, **options):
        dataset = get_dataset(options["dataset"])
        registry = default_registry(
            enable_search=options["search"], enable_web=not options["no_web"]
        )

        first = EnrichmentRecord.objects.filter(dataset=dataset).order_by("pk").first()
        seed = frozenset((first.seed or {}).keys()) if first else frozenset({"name"})
        total = EnrichmentRecord.objects.filter(dataset=dataset).count()

        self.stdout.write(f"dataset: {dataset.slug}")
        self.stdout.write(f"records: {total:,}")
        self.stdout.write(f"seed fields: {sorted(seed)}\n")
        for i, wave in enumerate(registry.plan(seed), 1):
            self.stdout.write(f"  wave {i}:")
            for name in wave:
                p = registry.get(name)
                self.stdout.write(
                    f"     {name:20s} cost={p.cost:7s} "
                    f"needs={sorted(p.requires) or '-'} -> {sorted(p.provides)}"
                )
        self.stdout.write(
            f"\nWorst case network calls: fetch<={total * 4:,}  search<={total:,}  "
            f"api<={total * 2:,} (SEC payloads already cached are free)"
        )
