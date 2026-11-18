"""Store a FRED series as it was known on a past date (an ALFRED vintage), DB-first.

The same service backs ``?vintage_date=`` on the observation endpoints, so a vintage
fetched here is served from the database there. Needs ``ENABLE_FRED_VINTAGES=true`` and
``FRED_API_KEY``.
"""

import logging

import requests
from django.core.management.base import BaseCommand, CommandError

from config.job_logging import ingest_job_context
from public_data.models import ExternalSeries
from public_data.services.sync import ensure_fred_series
from public_data.services.vintages import (
    VintageError,
    VintageUnavailable,
    check_vintage_date,
    stored_vintage,
    sync_series_vintage,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Fetch and store a FRED series as known on a past date (ALFRED vintage); "
        "needs ENABLE_FRED_VINTAGES and FRED_API_KEY."
    )

    def add_arguments(self, parser):
        parser.add_argument("--series", required=True, help="FRED series id, e.g. GDPC1.")
        parser.add_argument("--as-of", required=True, help="Vintage date, YYYY-MM-DD.")

    def handle(self, *args, **options):
        with ingest_job_context(logger, "sync_series_vintage") as fields:
            try:
                as_of = check_vintage_date(options["as_of"])
            except VintageError as exc:
                raise CommandError(str(exc)) from None
            external_id = options["series"].strip()
            fields["series"] = external_id
            fields["as_of"] = as_of.isoformat()
            series = ExternalSeries.objects.filter(provider="fred", external_id=external_id).first()
            if series is None:
                try:
                    series = ensure_fred_series(external_id)  # registers it, like a bundle load
                except (requests.RequestException, RuntimeError) as exc:
                    # Name the failure only: a requests error's text carries the API key.
                    raise CommandError(
                        f"could not register FRED series {external_id}: {type(exc).__name__}"
                    ) from None
            stored = stored_vintage(series, as_of)
            if stored:
                fields["observations"] = len(stored)
                self.stdout.write(
                    f"{external_id} as of {as_of}: already stored ({len(stored)} observations)"
                )
                return
            try:
                count = sync_series_vintage(series, as_of)
            except VintageUnavailable as exc:
                raise CommandError(str(exc)) from None
            fields["observations"] = count
            self.stdout.write(
                self.style.SUCCESS(f"{external_id} as of {as_of}: stored {count} observations")
            )
