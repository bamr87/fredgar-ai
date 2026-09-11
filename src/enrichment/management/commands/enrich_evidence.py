"""Print every claim and its source for one record — the audit view."""

from django.core.management.base import BaseCommand, CommandError

from enrichment.services import record_evidence

from ._base import add_dataset_argument, get_dataset


class Command(BaseCommand):
    help = "Show why a record says what it says."

    def add_arguments(self, parser):
        add_dataset_argument(parser)
        parser.add_argument("--name", required=True, help="Substring of the input name")

    def handle(self, *args, **options):
        data = record_evidence(get_dataset(options["dataset"]), options["name"])
        if data is None:
            raise CommandError(f"No record matching {options['name']!r}")

        self.stdout.write(f"{data['source_key']}  (record_id={data['record_id']})")
        if data["company_id"]:
            self.stdout.write(f"linked warehouse company: {data['company_id']}")
        self.stdout.write("")
        for c in data["claims"]:
            mark = "V" if c["verified"] else " "
            self.stdout.write(
                f"  [{mark}] {c['field']:22s} {str(c['value'])[:44]:46s} "
                f"{c['confidence']:.2f} {c['provider']}"
            )
            if c["evidence_url"]:
                self.stdout.write(f"        evidence: {c['evidence_url'][:92]}")
            elif c["evidence_locator"]:
                self.stdout.write(f"        locator:  {c['evidence_locator'][:92]}")

        contested = [g for g in data["golden"] if g["contested"]]
        if contested:
            self.stdout.write("\n  contested fields (review queue):")
            for g in contested:
                self.stdout.write(f"    {g['field']} = {g['value']} ({g['provider']})")
